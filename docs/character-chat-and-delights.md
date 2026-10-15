# Character chat and customer delights

Changes that make a visit warmer and give customers a reason to come back, based on research
on loyalty and conversation (goal-gradient, peak-end rule, surprise rewards, question-asking,
resuming interrupted tasks), with the founder's privacy rules on top.

## Chat with the stand character

- **Private.** The vendor never sees a customer's chat. The dashboard shows only food questions
  ("How much is jollof?", "Una get afang today?"). `services/character_chat.is_food_question`
  decides; when unsure it says no, and anything personal ("my exam", "I feel...") stays private
  even if it mentions food. Only food questions are saved to the msflib-conversation log, and the
  dashboard filters older saved messages again. The chat page tells customers this.
- **One short, warm chat per plate.** Each counted plate opens a chat of
  `CHAT_MESSAGES_PER_PLATE` (default 8) customer messages. The last reply answers the customer,
  then closes with a warm cliffhanger ("my pot don boil, come back and we go continue our gist").
  Never a guilt-trip. The chat opens again with the next plate. A guest with no plate cannot chat.
- **Picks up where it stopped.** The closing reply also gives one follow-up question
  (`FOLLOWUP:` line from the model, kept out of the reply). The next visit's opening line asks it
  once, then it is cleared.
- **Asks you back.** The prompt asks the character to end most replies with one light question
  about the customer's day or food mood; no health, money, family, religion or politics.
- **Remembers you, and you can see it.** A favourite dish (when they say they love one), the last
  dish talked about, and the follow-up question. Shown on the chat page with a "Forget all of
  this" button (`DELETE /public/{slug}/chat/memory`). Delete-my-data removes it.
- **Reasons to open the chat.** Quick buttons: "What should I eat today?" (a menu or special
  pick), "Any special today?", "Tell me a joke" (a curated, food-only joke of the day; no AI),
  "How do I get jara?". The opening line adds "Just ONE more plate" on plate 5 and today's special.
- Works without AI: every reply has a no-AI fallback, including the closing line.

Table: `chatmemory` (migration `scripts/migrations/2026-10-13_chat_memory.sql`).
Routes: `GET/POST /public/{slug}/chat`, `DELETE /public/{slug}/chat/memory`.

## Customer delights

- **Almost there.** Plate 5 says "Just ONE more plate and jara na yours!" with a pulsing
  "1 more!" badge on the card.
- **Plate 6 celebration and a warm goodbye.** The jara screen keeps its confetti and jumping
  character and adds a speech bubble; every counted plate ends with a short goodbye line.
- **Surprise jara.** Off until the vendor turns it on (`SURPRISE_JARA_ENABLED`). About one plate
  in `SURPRISE_JARA_ONE_IN` (15) that is not the jara plate also gets a jara, issued in the same
  transaction as the visit. Crew plates are never surprises. The customer sees "SURPRISE JARA!".
- **Today's special.** The vendor types it on the dashboard; the character announces it in the
  chat until midnight (Nigeria time).

Vendor routes: `GET /stands/{slug}/delights`, `PUT .../delights/surprise`, `PUT .../delights/special`.
Tests: `app/tests/api/api_v1/test_character_chat.py`.
