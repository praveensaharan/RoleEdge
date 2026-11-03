// The demo's data: everything the pipeline saved, from /api/demo/story (src/carecircle/chat/story.py).

let story = null;

export async function loadStory() {
  if (!story) {
    const response = await fetch("/api/demo/story");
    if (!response.ok) throw new Error(`Couldn't load the demo data (${response.status}). Is carecircle chat running?`);
    story = await response.json();
  }
  return story;
}

export const familyById = (id) => story.families.find((f) => f.id === id) || story.families[0];

/** The person an item was made for, e.g. {call_name: "Mummy", language: "Hindi", role: "parent"}. */
export const recipientOf = (family, item) => family.recipients.find((r) => r.key === item.recipient);
