"""One line-icon set, no emoji: cards and video frames draw icons, and stray emoji in model text are removed."""

import re
from typing import get_args

from roleedge.models import IconName
from roleedge.render import card_html
from roleedge.render.icons import ICONS, icon_svg
from roleedge.render.theme import strip_emoji
from roleedge.render.video import scene_html

from .conftest import make_digest

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


def test_every_icon_the_model_may_pick_can_be_drawn():
    assert set(get_args(IconName)) <= set(ICONS)
    assert icon_svg("bank", 40).startswith('<svg width="40"') and 'stroke="currentColor"' in icon_svg("bank")
    assert icon_svg("no-such-icon") == icon_svg("info")


def test_strip_emoji_keeps_words_in_every_script():
    assert strip_emoji("बिल भरें 📅 ✅ आज") == "बिल भरें आज"
    assert strip_emoji("締切 11月20日 ⏰") == "締切 11月20日"
    assert strip_emoji("₹1,846 · 2% → ok") == "₹1,846 · 2% → ok"
    assert strip_emoji(None) == ""


def test_cards_and_video_frames_use_icons_not_emoji(hindi_recipient):
    d = make_digest(illustration={"layout": "steps", "headline": "क्या करना है 📅",
                                  "panels": [{"icon": "bill", "heading": "बिल 🧾", "caption": "₹1,846"}]})
    for html in (card_html(d, hindi_recipient), scene_html(d.storyboard[0], 0, 1, False)):
        assert not EMOJI.search(html), EMOJI.findall(html)
        assert "<svg" in html


def test_the_demo_web_app_uses_no_emoji():
    from roleedge.config import DEMO_WEB_DIR

    found = {str(p.relative_to(DEMO_WEB_DIR)): EMOJI.findall(p.read_text(encoding="utf-8"))
             for p in DEMO_WEB_DIR.rglob("*") if p.suffix in (".html", ".css", ".js")}
    assert not {name: chars for name, chars in found.items() if chars}
