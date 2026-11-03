"""Studio: research first, propose the best way to explain it, then make it as moments for one person (a note in
your words, steps, a fridge card or two gentle questions for Mom; a picture story, a quiz game, an explore map or
questions for Grandma for a child), plus the family relay between grandparent and grandchild. See
docs/superpowers/specs/2026-11-02-studio-design.md."""

from .agents import MAKERS, Specialist, formats_for, grandparent_word
from .inputs import link_text
from .relay import Relay, pass_on
from .swarm import Source, Swarm
from .verify import check_pack, recipient_texts

__all__ = ["MAKERS", "Relay", "Source", "Specialist", "Swarm", "check_pack", "formats_for", "grandparent_word",
           "link_text", "pass_on", "recipient_texts"]
