"""The caregiver's talking avatar, built only with Meta models plus plain code (hackathon "strict" rules).

Muse Image draws the portrait and edits it into mouth and blink variants; SAM 3.1 finds the mouth and eyes in each;
code pastes only those regions onto the base portrait, so the face never shifts between frames. The parent's phone
then switches frames in time with the speech (``web/app/js/avatar.js``).
"""

from .build import AVATAR_DIR, PORTRAITS, build_avatar

__all__ = ["AVATAR_DIR", "PORTRAITS", "build_avatar"]
