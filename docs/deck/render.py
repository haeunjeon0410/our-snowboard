from playwright.sync_api import sync_playwright
import pathlib
p=pathlib.Path('index.html').resolve()
with sync_playwright() as pw:
    b=pw.chromium.launch(); pg=b.new_page(viewport={'width':1920,'height':1080})
    pg.goto(p.as_uri()); pg.wait_for_timeout(800)
    pg.pdf(path='Our-Snowboard_작품소개.pdf',width='1920px',height='1080px',print_background=True,prefer_css_page_size=True)
    b.close()
