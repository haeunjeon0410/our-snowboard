"""한글 점자 변환 (규칙 기반) + 역점역.

구현 범위: 초성·중성·종성, 약자(가·사, 나·다·마·바·자·카·타·파·하, 억·언·얼·연·열·영·옥·온·옹·운·울·은·을·인,
성·정·청, 것), 약어(그래서 등 7개), 숫자, 로마자(시작 ⠴ / 종료 ⠲, 대문자 ⠠), 주요 문장부호.
수식·화학식 같은 전문 점자는 범위 밖이며 '점역할 수 없는 글자'로 세어서 따로 보고한다.
"""
import re
import unicodedata

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = [""] + list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")
SP = "⠀"


def D(s: str) -> str:
    """점 번호 문자열('124') → 점자 한 칸"""
    return chr(0x2800 + sum(1 << (int(c) - 1) for c in s))


CHO_CELL = {"ㄱ": "4", "ㄴ": "14", "ㄷ": "24", "ㄹ": "5", "ㅁ": "15", "ㅂ": "45", "ㅅ": "6", "ㅇ": "",
            "ㅈ": "46", "ㅊ": "56", "ㅋ": "124", "ㅌ": "125", "ㅍ": "145", "ㅎ": "245"}
TENSE = {"ㄲ": "ㄱ", "ㄸ": "ㄷ", "ㅃ": "ㅂ", "ㅆ": "ㅅ", "ㅉ": "ㅈ"}
JUNG_CELL = {"ㅏ": ["126"], "ㅑ": ["345"], "ㅓ": ["234"], "ㅕ": ["156"], "ㅗ": ["136"], "ㅛ": ["346"],
             "ㅜ": ["134"], "ㅠ": ["146"], "ㅡ": ["246"], "ㅣ": ["135"], "ㅐ": ["1235"], "ㅔ": ["1345"],
             "ㅒ": ["345", "1235"], "ㅖ": ["34"], "ㅘ": ["1236"], "ㅙ": ["1236", "1235"], "ㅚ": ["13456"],
             "ㅝ": ["1234"], "ㅞ": ["1234", "1235"], "ㅟ": ["134", "1235"], "ㅢ": ["2456"]}
JONG_CELL = {"ㄱ": ["1"], "ㄲ": ["1", "1"], "ㄳ": ["1", "3"], "ㄴ": ["25"], "ㄵ": ["25", "13"], "ㄶ": ["25", "356"],
             "ㄷ": ["35"], "ㄹ": ["2"], "ㄺ": ["2", "1"], "ㄻ": ["2", "26"], "ㄼ": ["2", "12"], "ㄽ": ["2", "3"],
             "ㄾ": ["2", "236"], "ㄿ": ["2", "256"], "ㅀ": ["2", "356"], "ㅁ": ["26"], "ㅂ": ["12"], "ㅄ": ["12", "3"],
             "ㅅ": ["3"], "ㅆ": ["34"], "ㅇ": ["2356"], "ㅈ": ["13"], "ㅊ": ["23"], "ㅋ": ["235"], "ㅌ": ["236"],
             "ㅍ": ["256"], "ㅎ": ["356"]}
# 받침이 있는 글자의 약자: (모음, 받침) → 점
FINAL_ABBR = {
    ("ㅓ", "ㄱ"): "1456", ("ㅓ", "ㄴ"): "23456", ("ㅓ", "ㄹ"): "2345", ("ㅕ", "ㄴ"): "16", ("ㅕ", "ㄹ"): "1256",
    ("ㅕ", "ㅇ"): "12456", ("ㅗ", "ㄱ"): "1346", ("ㅗ", "ㄴ"): "12356", ("ㅗ", "ㅇ"): "123456",
    ("ㅜ", "ㄴ"): "1245", ("ㅜ", "ㄹ"): "12346", ("ㅡ", "ㄴ"): "1356", ("ㅡ", "ㄹ"): "2346", ("ㅣ", "ㄴ"): "12345"}
WORD_ABBR = {"그래서": ["1", "234"], "그러나": ["1", "14"], "그러면": ["1", "25"], "그러므로": ["1", "26"],
             "그런데": ["1", "1345"], "그리고": ["1", "136"], "그리하여": ["1", "156"]}
A_OMIT = set("ㄴㄷㅁㅂㅈㅋㅌㅍㅎ")  # '나 다 마 바 자 카 타 파 하' : 받침이 없을 때 초성만 적는다

PUNCT = {".": ["256"], ",": ["5"], "?": ["236"], "!": ["235"], ":": ["5", "2"], ";": ["56", "23"],
         "(": ["236", "3"], ")": ["6", "356"], "-": ["36"], "–": ["36", "36"], "—": ["36", "36"],
         "~": ["4", "35"], "/": ["456", "34"], "·": ["5", "23"], "※": ["5", "35"], "…": ["6", "6", "6"],
         "'": ["3"], "[": ["236", "23"], "]": ["56", "356"], "•": ["5", "23"]}
QUOTE_OPEN = {'"': ["236"], "“": ["236"], "‘": ["6", "236"], "'": ["6", "236"]}
QUOTE_CLOSE = {'"': ["356"], "”": ["356"], "’": ["356", "3"], "'": ["356", "3"]}
PUNCT_COLLIDE = {D("256"), D("236"), D("235"), D("356")}  # 받침 ㅍ·ㅌ·ㅋ·ㅎ과 같은 점

LATIN = dict(zip("abcdefghijklmnopqrstuvwxyz",
                 ["1", "12", "14", "145", "15", "124", "1245", "125", "24", "245", "13", "123", "134", "1345",
                  "135", "1234", "12345", "1235", "234", "2345", "136", "1236", "2456", "1346", "13456", "1356"]))
DIGIT = dict(zip("1234567890", ["1", "12", "14", "145", "15", "124", "1245", "125", "24", "245"]))
NUM = D("3456")
ROMAN_START, ROMAN_END, CAP = D("356"), D("256"), D("6")
HYPHEN = D("36")
SET_FOR_HYPHEN = set("ㄴㄷㅁㅋㅌㅍㅎ")


def _cells(lst):
    return "".join(D(x) for x in lst)


def _parts(ch):
    code = ord(ch) - 0xAC00
    return CHO[code // 588], JUNG[(code % 588) // 28], JONG[code % 28]


def _init_cells(cho):
    if cho in TENSE:
        return D("6") + D(CHO_CELL[TENSE[cho]])
    return D(CHO_CELL[cho]) if CHO_CELL[cho] else ""


def enc_syllable(ch: str, nxt: str | None = None) -> str:
    """음절 하나를 점자로. nxt: 같은 낱말 안에서 바로 뒤따르는 한글(있으면). 제17항 때문에 필요."""
    cho, jung, jong = _parts(ch)
    if ch == "것":                       # 제12항 약자
        return D("456") + D("234")
    if ch == "팠":                       # 제17항 [붙임]: '팠'은 ㅏ를 생략하지 않는다 ('폐'와 구별)
        return D("145") + _cells(JUNG_CELL["ㅏ"]) + _cells(JONG_CELL["ㅆ"])
    if ch == "껏":                       # 제14항: 된소리표 + 것
        return D("6") + D("456") + D("234")
    if cho in "ㅅㅆㅈㅉㅊ" and jung == "ㅓ" and jong == "ㅇ":   # 제16항: 성·썽·정·쩡·청
        return _init_cells(cho) + D("12456")
    if (jung, jong) in FINAL_ABBR:       # 제12항: 억 언 얼 연 열 영 옥 온 옹 운 울 은 을 인
        return _init_cells(cho) + D(FINAL_ABBR[(jung, jong)])
    if jung == "ㅏ":
        if cho in ("ㄱ", "ㄲ"):          # 가·까
            return (D("6") if cho == "ㄲ" else "") + D("1246") + _cells(JONG_CELL.get(jong, []))
        if cho in ("ㅅ", "ㅆ"):          # 사·싸
            return (D("6") if cho == "ㅆ" else "") + D("123") + _cells(JONG_CELL.get(jong, []))
        if cho in A_OMIT or TENSE.get(cho) in A_OMIT:
            # 제12·13항: 나·다·마·바·자·카·타·파·하(·따·빠·짜)는 받침이 있어도 ㅏ를 생략한 약자로 쓴다
            # 제17항: 받침이 없고 뒤에 모음으로 시작하는 음절이 이어지면 ㅏ를 생략하지 않는다 (단, '예'는 붙임표가 있어 생략)
            if jong == "" and nxt is not None and _HANGUL.match(nxt):
                n_cho, n_jung, _ = _parts(nxt)
                if n_cho == "ㅇ" and n_jung != "ㅖ":
                    return _init_cells(cho) + _cells(JUNG_CELL["ㅏ"])
            return _init_cells(cho) + _cells(JONG_CELL.get(jong, []))
    return _init_cells(cho) + _cells(JUNG_CELL[jung]) + _cells(JONG_CELL.get(jong, []))


def needs_hyphen(prev: str | None, cur: str) -> bool:
    """제10항·제11항: 모음 뒤에 '예'가, 또는 ㅑ·ㅘ·ㅜ·ㅝ 뒤에 '애'가 이어지면 사이에 붙임표를 적는다."""
    if not prev or not _HANGUL.match(prev):
        return False
    p_cho, p_jung, p_jong = _parts(prev)
    c_cho, c_jung, _ = _parts(cur)
    if p_jong != "" or c_cho != "ㅇ":
        return False
    if c_jung == "ㅖ":
        return True
    return c_jung == "ㅐ" and p_jung in ("ㅑ", "ㅘ", "ㅜ", "ㅝ")


# ──────────────── 글 → 점자 ────────────────
_HANGUL = re.compile(r"[가-힣]")


def _is_latin(c):
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def _enc_word_latin(w: str) -> str:
    out = []
    if len(w) >= 2 and w.isupper() and w.isalpha():
        return CAP + CAP + "".join(D(LATIN[c.lower()]) for c in w)
    for c in w:
        if c.isalpha():
            out.append((CAP if c.isupper() else "") + D(LATIN[c.lower()]))
        elif c.isdigit():
            out.append(NUM + D(DIGIT[c]))
        elif c == "-":
            out.append(HYPHEN)
    return "".join(out)


def encode(text: str, stats: dict | None = None) -> str:
    """한 줄/문단의 글을 유니코드 점자로. stats에 점역하지 못한 글자를 센다."""
    text = unicodedata.normalize("NFC", text)
    stats = stats if stats is not None else {}
    stats.setdefault("unmapped", {})
    stats.setdefault("chars", 0)
    out = []
    i, n = 0, len(text)
    quote_open = {}
    # 약어: 낱말 단위로 먼저 처리
    while i < n:
        c = text[i]
        # 공백
        if c in " \t 　":
            if out and out[-1] != SP:
                out.append(SP)
            i += 1
            continue
        if c == "\n":
            out.append("\n")
            i += 1
            continue
        # 약어 (낱말 전체가 일치할 때)
        if _HANGUL.match(c) and (i == 0 or not _HANGUL.match(text[i - 1])):
            j = i
            while j < n and _HANGUL.match(text[j]):
                j += 1
            w = text[i:j]
            if w in WORD_ABBR and (j >= n or not (_is_latin(text[j]) or text[j].isdigit())):
                out.append(_cells(WORD_ABBR[w]))
                stats["chars"] += len(w)
                i = j
                continue
        if _HANGUL.match(c):
            prev = text[i - 1] if i > 0 else None
            nxt = text[i + 1] if i + 1 < n else None
            if needs_hyphen(prev, c):
                out.append(HYPHEN)
            out.append(enc_syllable(c, nxt))
            stats["chars"] += 1
            i += 1
            continue
        # 숫자
        if c.isdigit() and c in DIGIT:
            j = i
            while j < n and (text[j] in DIGIT or (text[j] in ",.-" and j + 1 < n and text[j + 1] in DIGIT and j > i)):
                j += 1
            num = text[i:j]
            cells = NUM
            for ch in num:
                cells += D(DIGIT[ch]) if ch in DIGIT else (D("2") if ch == "," else HYPHEN if ch == "-" else D("256"))
            out.append(cells)
            stats["chars"] += len(num)
            i = j
            if j < n and _HANGUL.match(text[j]):
                # 규정: 숫자와 혼동되는 ㄴㄷㅁㅋㅌㅍㅎ 첫소리와 '운' 약자가 숫자 다음에 이어지면 띄어 쓴다
                if CHO[(ord(text[j]) - 0xAC00) // 588] in SET_FOR_HYPHEN or text[j] == "운":
                    out.append(SP)
            continue
        # 로마자: 낱말들을 묶어서 ⠴ … ⠲ 로 감싼다
        if _is_latin(c):
            j = i
            words = []
            while True:
                k = j
                while k < n and (_is_latin(text[k]) or (text[k] in DIGIT) or (text[k] == "-" and k + 1 < n and _is_latin(text[k + 1]))):
                    k += 1
                if k == j:
                    break
                words.append(text[j:k])
                j = k
                # 공백 뒤에 또 로마자가 오면 같은 묶음
                if j < n and text[j] == " " and j + 1 < n and _is_latin(text[j + 1]):
                    words.append(" ")
                    j += 1
                    continue
                break
            cells = ROMAN_START + "".join(SP if w == " " else _enc_word_latin(w) for w in words) + ROMAN_END
            out.append(cells)
            stats["chars"] += sum(len(w) for w in words)
            i = j
            continue
        # 따옴표
        if c in "\"“”‘’'":
            if c in "“‘" or (c in "\"'" and not quote_open.get(c)):
                out.append(_cells(QUOTE_OPEN[c]))
                quote_open[c] = True
            else:
                out.append(_cells(QUOTE_CLOSE[c]))
                quote_open[c] = False
            stats["chars"] += 1
            i += 1
            continue
        if c in PUNCT:
            out.append(_cells(PUNCT[c]))
            stats["chars"] += 1
            i += 1
            continue
        # 점역할 수 없는 글자
        if not unicodedata.category(c).startswith("C"):
            stats["unmapped"][c] = stats["unmapped"].get(c, 0) + 1
        i += 1
    return "".join(out)


# ──────────────── 점자 → 글 (역점역) ────────────────
LEX = {}
for _code in range(0xAC00, 0xD7A4):
    _ch = chr(_code)
    LEX.setdefault(enc_syllable(_ch), _ch)
    # ㅏ를 밝혀 적은 형태(제17항)도 같은 글자로 읽는다: '다음' = ⠊⠣⠪⠢
    _cho, _jung, _jong = _parts(_ch)
    if _jung == "ㅏ" and _jong == "" and (_cho in A_OMIT or TENSE.get(_cho) in A_OMIT):
        LEX.setdefault(_init_cells(_cho) + _cells(JUNG_CELL["ㅏ"]), _ch)
_MAXLEN = max(len(k) for k in LEX)
_WORD_LEX = {_cells(v): k for k, v in WORD_ABBR.items()}
_LATIN_INV = {D(v): k for k, v in LATIN.items()}
_DIGIT_INV = {D(v): k for k, v in DIGIT.items()}
_PUNCT_INV = {}
for _k, _v in PUNCT.items():
    _PUNCT_INV.setdefault(_cells(_v), _k)
for _k, _v in QUOTE_OPEN.items():
    _PUNCT_INV.setdefault(_cells(_v), _k)
for _k, _v in QUOTE_CLOSE.items():
    _PUNCT_INV.setdefault(_cells(_v), _k)
_PUNCT_INV[_cells(PUNCT["'"])] = "'"
_PUNCT_INV[_cells(QUOTE_OPEN['"'])] = '"'   # ⠦ 는 열기 따옴표/물음표가 겹침. 문맥으로 정함
_PUNCT_KEYS = sorted(_PUNCT_INV, key=len, reverse=True)
INF = 1e9


def _latin_seg(s: str, i: int):
    """s[i]=⠴ 에서 시작하는 로마자 묶음. (끝 위치, 글) 또는 None"""
    j = i + 1
    out, caps_word, cap1 = [], False, False
    while j < len(s):
        c = s[j]
        if c == ROMAN_END:
            return (j + 1, "".join(out)) if out else None
        if c == CAP:
            if j + 1 < len(s) and s[j + 1] == CAP:
                caps_word = True
                j += 2
            else:
                cap1 = True
                j += 1
            continue
        if c == SP:
            out.append(" ")
            caps_word = False
        elif c in _LATIN_INV:
            ch = _LATIN_INV[c]
            out.append(ch.upper() if (caps_word or cap1) else ch)
            cap1 = False
        elif c == NUM and j + 1 < len(s) and s[j + 1] in _DIGIT_INV:
            out.append(_DIGIT_INV[s[j + 1]])
            j += 2
            continue
        elif c == HYPHEN:
            out.append("-")
        else:
            return None
        j += 1
    return None


def decode_line(s: str) -> str:
    """점자 한 줄을 글로. 같은 규칙표를 거꾸로 적용한다 (동적 계획법으로 가장 그럴듯한 끊기를 찾는다)."""
    n = len(s)
    best = [INF] * (n + 1)
    back = [None] * (n + 1)
    best[0] = 0.0

    def tok_start(p):
        return p == 0 or s[p - 1] == SP

    def tok_end(p):
        return p == n or s[p] == SP

    # 열린 따옴표가 있으면 뒤따르는 ⠴ 는 닫는 따옴표, 아니면 로마자 시작. ')' (⠠⠴) 의 ⠴ 도 로마자가 아니다.
    forbid_latin, pending, q = set(), 0, 0
    while q < n:
        ch = s[q]
        if ch == D("236") and tok_start(q) and q + 1 < n and s[q + 1] not in (SP, D("3")):
            pending += 1
        elif ch == ROMAN_START:
            after_open = q > 0 and s[q - 1] == D("236") and pending > 0   # 여는 따옴표 바로 뒤 ⠴ 는 로마자 시작
            if (q > 0 and s[q - 1] == CAP) or (pending > 0 and not after_open):
                forbid_latin.add(q)
                if pending > 0 and not (q > 0 and s[q - 1] == CAP):
                    pending -= 1
            else:
                r = _latin_seg(s, q)
                if r:
                    q = r[0]
                    continue
        q += 1

    for p in range(n):
        if best[p] >= INF:
            continue
        c = s[p]

        def relax(q, cost, text):
            if best[p] + cost < best[q]:
                best[q] = best[p] + cost
                back[q] = (p, text)

        if c == SP:
            relax(p + 1, 0.0, " ")
            continue
        # 숫자
        if c == NUM and p + 1 < n and s[p + 1] in _DIGIT_INV:
            q, digs = p + 1, ""
            while q < n:
                if s[q] in _DIGIT_INV:
                    digs += _DIGIT_INV[s[q]]
                elif s[q] in (D("2"), D("256"), HYPHEN) and q + 1 < n and s[q + 1] in _DIGIT_INV and digs:
                    digs += "," if s[q] == D("2") else ("-" if s[q] == HYPHEN else ".")
                else:
                    break
                q += 1
            relax(q, 0.3, digs)
        # 로마자
        if c == ROMAN_START and p not in forbid_latin:
            r = _latin_seg(s, p)
            if r:
                # 낱말 중간(앞이 한글·점자 글자)에서 갑자기 시작하는 로마자는 받침 ㅎ일 가능성이 커서 비용을 높인다
                glued = (not tok_start(p)) and s[p - 1] not in (D("236"), D("3"))
                relax(r[0], 3.0 if glued else 0.5, r[1])
        # 제10·11항 붙임표: 뒤에 '예' 또는 '애'가 이어질 때는 글자 없는 구조 표시
        if c == HYPHEN and p > 0 and not tok_start(p) and s[p + 1:p + 2] in (D("34"), D("1235")):
            relax(p + 1, 0.15, "")
        # 약어
        if tok_start(p):
            for k, w in _WORD_LEX.items():
                if s.startswith(k, p) and (p + len(k) == n or s[p + len(k)] == SP or s[p + len(k)] in _PUNCT_INV):
                    relax(p + len(k), 0.5, w)
        # 글자
        for L in range(1, _MAXLEN + 1):
            seg = s[p:p + L]
            if len(seg) < L:
                break
            if seg in LEX:
                end = p + L
                cost = 1.0
                if tok_end(end) and seg[-1] in PUNCT_COLLIDE:
                    cost += 1.0   # 낱말 끝의 ⠲ ⠦ ⠖ ⠴ 는 문장부호로 읽는 쪽을 선호
                if seg[-1] == ROMAN_START and (end - 1) in forbid_latin:
                    cost += 3.0   # 열린 따옴표 뒤의 ⠴ 는 받침 ㅎ이 아니라 닫는 따옴표
                relax(end, cost, LEX[seg])
        # 문장부호
        for k in _PUNCT_KEYS:
            if s.startswith(k, p):
                end = p + len(k)
                collide = k in PUNCT_COLLIDE or any(x in PUNCT_COLLIDE for x in k)
                text = _PUNCT_INV[k]
                if collide and k in PUNCT_COLLIDE:
                    cost = 0.2 if (tok_start(p) or tok_end(end)) else 4.0
                    if k == D("236"):
                        text = "?" if tok_end(end) else '"'
                    elif k == D("356"):
                        text = '"'
                        cost = 0.8 if p in forbid_latin else cost
                else:
                    cost = 0.5
                relax(end, cost, text)
        # 읽을 수 없는 칸은 건너뛴다
        relax(p + 1, 6.0, "")
    # 복원
    res, p = [], n
    while p > 0:
        pp, t = back[p]
        res.append(t)
        p = pp
    out = "".join(reversed(res))
    # 열기·닫기 따옴표 정리: 짝수 번째 ⠦ 로 읽힌 큰따옴표는 그대로 둔다
    return out


def decode(braille: str) -> str:
    return "\n".join(decode_line(l) for l in braille.split("\n"))


# ──────────────── 줄 나누기, BRF ────────────────
_ASCII_BRAILLE = " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)="


def to_brf(braille: str) -> str:
    """유니코드 점자 → 북미 ASCII 점자(BRF). 점자 프린터용"""
    out = []
    for ch in braille:
        if "⠀" <= ch <= "⠿":
            out.append(_ASCII_BRAILLE[ord(ch) - 0x2800])
        else:
            out.append(ch)
    return "".join(out)


def wrap(braille: str, width=32) -> list[str]:
    lines = []
    for para in braille.split("\n"):
        cur = ""
        for w in para.split(SP):
            if not w:
                continue
            while len(w) > width:
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(w[:width])
                w = w[width:]
            if not cur:
                cur = w
            elif len(cur) + 1 + len(w) <= width:
                cur += SP + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def normalize_for_compare(text: str) -> str:
    """역점역 비교용: 점역 대상 글자(한글·숫자·로마자·주요 부호)만 남기고 따옴표 모양을 맞춘다."""
    t = unicodedata.normalize("NFC", text)
    out = []
    for c in t:
        if _HANGUL.match(c) or c in DIGIT or _is_latin(c) or c in PUNCT or c in "\"“”‘’'":
            if c in "“”":
                c = '"'
            if c in "‘’":
                c = "'"
            if c in "—–":      # 줄표(——)와 물결표 앞뒤 대시는 점형이 같다
                c = "–"
            out.append(c)
    return "".join(out)
