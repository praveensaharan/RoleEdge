// What every part of the caregiver's Studio shares: the open circle and its items, the words for the formats, and a
// quiet notice for errors (instead of the browser's alert box).
import { esc } from "../common.js";

// Each person gets their own moments: something to do with the family, not a document to study.
const PARENT_FORMATS = ["note", "steps", "map", "askme", "video", "picture", "card"];
const CHILD_FORMATS = ["story", "quiz", "map", "video", "picture", "relay"];
export const FORMATS = [...new Set([...PARENT_FORMATS, ...CHILD_FORMATS])];
export const FORMAT_TEXT = { // [name, what it is] as the caregiver reads them
  note: ["In your words", "A short note as you'd say it, read aloud"], steps: ["Slides", "One step per slide, at her own pace"],
  card: ["Fridge card", "One page to keep, or print"], askme: ["Quiz", "Two gentle questions; her answers come to you"],
  story: ["Picture story", "Read aloud, page by page"], quiz: ["Quiz game", "Stars, and no wrong-answer buzzer"],
  map: ["Mind map", "The key idea in the middle, its parts around it"], relay: ["Ask {grandparent}", "Questions to ask, passed on by the family relay"],
  video: ["Animated video", "Narrated scenes that play by themselves"], picture: ["Picture", "One illustration, drawn by Muse Image"],
};

export const state = {
  circles: [], circle: null, engine: "", items: [], link: null, tab: "stream", mode: "studio", voice: "mine",
  to: "", // who the next share is for: "" = the parent, or a child's id
  ref: null, // a page from a connected app: { ref: "notion:<id>", title, app }
  picks: {}, files: [], viewers: {}, recorder: null,
  ownVoice: null, // { id, recorder } while you record your own voice for a quick message
  scenes: { id: null, open: false, closed: false }, // behind the scenes: which share, open, closed by you
};

export const $ = (id) => document.getElementById(id);
export const parent = () => state.circle.parent;
export const her = () => parent().call_name;
export const me = () => state.circle.caregiver.call_name;
/** Her language as a `lang` attribute value, so screen readers and fonts treat her words correctly. */
export const herLang = () => parent().language || "en";

/** Everyone a share can be for: the parent first, then the caregiver's children. */
export const recipients = () => [parent(), ...(state.circle.children || [])];
/** Who the next share is for. */
export const recipient = () => recipients().find((m) => m.id === state.to) || parent();
/** Who a share was for (older shares are the parent's). */
export const recipientOf = (item) => recipients().find((m) => m.id === item.payload.recipient) || parent();
export const isChild = (member) => member.role === "child";
export const formatsFor = (member) => (isChild(member) ? CHILD_FORMATS : PARENT_FORMATS);
/** What a person calls their caregiver and their grandparent, for the names of their moments. */
export const namesFor = (member) => ({
  caregiver: member.calls_caregiver || state.circle.caregiver.call_name_local || me(),
  grandparent: member.calls_grandparent || parent().call_name,
});
/** A moment's name and description for the caregiver, for `member`. */
export const formatText = (format, member) => (FORMAT_TEXT[format] || [format, ""]).map((t) => t.replace("{grandparent}", isChild(member) ? namesFor(member).grandparent : her()));
export const clock = (at) => new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** A short notice at the bottom of the page; errors stay until dismissed, others fade after a few seconds. */
export function notify(message, { error = true } = {}) {
  let box = $("notice");
  if (!box) {
    box = Object.assign(document.createElement("div"), { id: "notice", className: "notice" });
    document.body.append(box);
  }
  box.setAttribute("role", error ? "alert" : "status");
  box.classList.toggle("error", error);
  box.innerHTML = `<span>${esc(message)}</span><button type="button" class="btn ghost sm">Dismiss</button>`;
  box.hidden = false;
  box.querySelector("button").onclick = () => { box.hidden = true; };
  clearTimeout(notify.timer);
  if (!error) notify.timer = setTimeout(() => { box.hidden = true; }, 5000);
}
