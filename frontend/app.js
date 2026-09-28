// Chat-driven front end -- no build step, no frameworks. A small state
// machine drives the conversation; the actual verification still goes
// through the same POST /api/analyze the old form-based UI used.

const chatLog = document.getElementById("chat-log");
const composer = document.getElementById("composer");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");
const attachBtn = document.getElementById("attach-btn");
const fileInput = document.getElementById("file-input");
const attachmentChip = document.getElementById("attachment-chip");
const attachmentName = document.getElementById("attachment-name");
const attachmentRemove = document.getElementById("attachment-remove");

const LABEL_META = {
  legitimate: { text: "Looks legitimate", icon: "✅" },
  likely_fake: { text: "Likely fake", icon: "⚠️" },
  scam: { text: "Likely a scam", icon: "⚠️" },
  uncertain: { text: "Uncertain — not enough evidence", icon: "❔" },
};

const PROGRESS_MESSAGES = [
  "Reading the message…",
  "Searching for matching reports…",
  "Putting together your answer…",
  "Creating your awareness graphic…",
];

// --- Conversation state -----------------------------------------------
// STATE machine keeps this file readable without a framework:
//   AWAITING_SUBMISSION  -- waiting for the first message/link/file
//   AWAITING_CONTEXT     -- asked "where did this come from?", waiting for a reply or Skip
//   ANALYZING            -- request in flight, composer effectively paused
//   READY_FOR_FEEDBACK   -- verdict shown, waiting for a thumbs up/down (or a new message)
//   AWAITING_FEEDBACK_MSG-- asked "what would've made this better?" after a thumbs down
let state = "AWAITING_SUBMISSION";
let pendingAttachment = null; // File object, or null
let pendingSubmission = null; // { text, file } captured at first submit
let lastVerdictLabel = null; // for the feedback payload
let progressTimer = null;

// --- Rendering helpers ---------------------------------------------------

function scrollToBottom() {
  chatLog.scrollTop = chatLog.scrollHeight;
}

function appendBotMessage(content, { asHTML = false } = {}) {
  const row = document.createElement("div");
  row.className = "msg-row bot";
  const bubble = document.createElement("div");
  bubble.className = "bubble bot";
  if (asHTML) {
    bubble.innerHTML = content;
  } else if (content.includes("\n")) {
    // Plain multi-line canned messages (e.g. bullet lists) need <br>,
    // since bubble.textContent would otherwise collapse the newlines.
    bubble.innerHTML = escapeHTML(content).replaceAll("\n", "<br>");
  } else {
    bubble.textContent = content;
  }
  row.appendChild(bubble);
  chatLog.appendChild(row);
  scrollToBottom();
  return bubble;
}

function appendUserMessage(text, fileLabel) {
  const row = document.createElement("div");
  row.className = "msg-row user";
  const bubble = document.createElement("div");
  bubble.className = "bubble user";
  if (fileLabel) {
    const tag = document.createElement("div");
    tag.className = "file-tag";
    tag.textContent = `📎 ${fileLabel}`;
    bubble.appendChild(tag);
  }
  if (text) {
    const p = document.createElement("div");
    p.textContent = text;
    bubble.appendChild(p);
  }
  row.appendChild(bubble);
  chatLog.appendChild(row);
  scrollToBottom();
}

// Quick-reply pills rendered inside a bot bubble. `options` is an array of
// { label, onClick }. Buttons remove themselves after one is clicked so the
// user can't reply to a stale question twice.
function appendQuickReplies(options) {
  const row = document.createElement("div");
  row.className = "msg-row bot";
  const wrap = document.createElement("div");
  wrap.className = "quick-replies";
  options.forEach(({ label, onClick }) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "quick-reply";
    btn.textContent = label;
    btn.addEventListener("click", () => {
      wrap.remove();
      onClick();
    });
    wrap.appendChild(btn);
  });
  row.appendChild(wrap);
  chatLog.appendChild(row);
  scrollToBottom();
}

function setComposerEnabled(enabled) {
  textInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
  attachBtn.disabled = !enabled;
}

// --- Attachment handling --------------------------------------------------

attachBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;
  pendingAttachment = file;
  attachmentName.textContent = file.name;
  attachmentChip.classList.remove("hidden");
});

attachmentRemove.addEventListener("click", () => {
  pendingAttachment = null;
  fileInput.value = "";
  attachmentChip.classList.add("hidden");
});

function clearAttachment() {
  pendingAttachment = null;
  fileInput.value = "";
  attachmentChip.classList.add("hidden");
}

// --- Greeting -------------------------------------------------------------

function greet() {
  appendBotMessage(
    "Hi — I'm here to help you check if something's real or a scam. " +
      "You can paste a message, drop in a link, or attach a screenshot, image, or video. " +
      "No judgment either way — a lot of these are designed to fool anyone. What have you got?"
  );
}

// --- Composer submit --------------------------------------------------

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = textInput.value.trim();
  const file = pendingAttachment;

  if (state === "ANALYZING") {
    // Ignore stray submits while a request is already in flight.
    return;
  }

  if (state === "AWAITING_FEEDBACK_MSG") {
    if (!text) return;
    appendUserMessage(text);
    submitFeedback({ helpful: false, message: text });
    resetInputs();
    return;
  }

  // READY_FOR_FEEDBACK: treat a fresh message as starting a new check
  // rather than forcing the user through the feedback prompt first.
  if (state === "READY_FOR_FEEDBACK") {
    state = "AWAITING_SUBMISSION";
  }

  if (state === "AWAITING_SUBMISSION") {
    if (!text && !file) {
      appendBotMessage("Paste a message or link, or attach a file, and I'll take a look.");
      return;
    }
    pendingSubmission = { text: text || null, file };
    appendUserMessage(text, file ? file.name : null);
    resetInputs();

    appendBotMessage("Got it, looking at that now. 🔍");
    appendBotMessage(
      "Quick question while I check — where did this come from? " +
        "(WhatsApp forward, text message, email, something else)"
    );
    appendQuickReplies([{ label: "Skip this", onClick: () => runAnalysis(null) }]);
    state = "AWAITING_CONTEXT";
    return;
  }

  if (state === "AWAITING_CONTEXT") {
    const note = text || null;
    if (note) appendUserMessage(note);
    resetInputs();
    runAnalysis(note);
    return;
  }
});

function resetInputs() {
  textInput.value = "";
  clearAttachment();
}

// --- Analysis ---------------------------------------------------------

function startProgressMessage() {
  let i = 0;
  const bubble = appendBotMessage(PROGRESS_MESSAGES[0]);
  progressTimer = setInterval(() => {
    i = (i + 1) % PROGRESS_MESSAGES.length;
    bubble.textContent = PROGRESS_MESSAGES[i];
    scrollToBottom();
  }, 1600);
  return bubble;
}

function stopProgressMessage(bubble, finalText) {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  if (finalText) {
    bubble.textContent = finalText;
  } else {
    bubble.parentElement.remove();
  }
}

async function runAnalysis(note) {
  state = "ANALYZING";
  setComposerEnabled(false);
  const progressBubble = startProgressMessage();

  const formData = new FormData();
  if (pendingSubmission.text) formData.append("text", pendingSubmission.text);
  if (pendingSubmission.file) formData.append("file", pendingSubmission.file);
  if (note) formData.append("note", note);

  try {
    const response = await fetch("/api/analyze", { method: "POST", body: formData });
    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      const message = (payload && payload.detail) || `Request failed (${response.status}).`;
      throw new Error(message);
    }

    stopProgressMessage(progressBubble, null);
    setComposerEnabled(true);
    renderVerdict(payload);
  } catch (error) {
    stopProgressMessage(
      progressBubble,
      `Sorry, something went wrong: ${error.message || "please try again."}`
    );
    setComposerEnabled(true);
    state = "AWAITING_SUBMISSION";
  }
}

// --- Rendering the verdict + guided next step --------------------------

function renderVerdict(payload) {
  const verdict = payload.verdict;
  lastVerdictLabel = verdict.label;
  const meta = LABEL_META[verdict.label] || { text: verdict.label, icon: "" };
  const confidencePct = Math.round(verdict.confidence * 100);

  let html = `<div class="badge ${verdict.label}">${meta.icon} ${meta.text} (${confidencePct}% confidence)</div>`;
  html += `<p>${escapeHTML(verdict.summary)}</p>`;

  if (verdict.red_flags && verdict.red_flags.length > 0) {
    html += `<div class="section-label">Red flags found</div><ul>`;
    verdict.red_flags.forEach((flag) => {
      html += `<li>${escapeHTML(flag)}</li>`;
    });
    html += `</ul>`;
  }

  if (verdict.sources && verdict.sources.length > 0) {
    html += `<div class="section-label">Sources used</div><ul>`;
    verdict.sources.forEach((source) => {
      html += `<li><a href="${escapeAttr(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(
        source.title
      )}</a> — ${escapeHTML(source.note)}</li>`;
    });
    html += `</ul>`;
  }

  if (payload.warning_image_url) {
    html += `<div class="section-label">Shareable awareness image</div>`;
    html += `<img class="warning-image" src="${escapeAttr(payload.warning_image_url)}" alt="AI-generated awareness graphic about the checked content" />`;
    html += `<a class="download-link" href="${escapeAttr(
      payload.warning_image_url
    )}" download="awareness-graphic.png">Download to share</a>`;
  }

  appendBotMessage(html, { asHTML: true });

  renderGuidedNextStep(verdict.label);
}

function renderGuidedNextStep(label) {
  if (label === "scam" || label === "likely_fake") {
    appendBotMessage(
      "Here's what I'd do right now:\n" +
        "• Don't click the link or reply\n" +
        "• Don't share any OTP, PIN, or payment info if you haven't already\n" +
        "• Block the sender"
    );
    appendQuickReplies([
      {
        label: "I already clicked or paid something",
        onClick: showAlreadyClickedAdvice,
      },
    ]);
  } else if (label === "uncertain") {
    appendBotMessage(
      "Since this isn't confirmed either way, I'd treat it cautiously — verify with the official " +
        "source directly before acting on it."
    );
  } else {
    appendBotMessage("Glad that's sorted. Anything else you want me to check?");
  }

  askForFeedback();
}

function showAlreadyClickedAdvice() {
  appendBotMessage(
    "That happens more than you'd think — here's how to limit the damage:\n" +
      "• If you entered a password: change it immediately, on that site and anywhere you reused it\n" +
      "• If you shared an OTP or card details: call your bank's official number (not one from the message) and freeze the card\n" +
      "• If you paid via UPI/bank transfer: report it to your bank and to cybercrime.gov.in (if you're in India) right away\n" +
      "• Keep a screenshot of the message as evidence"
  );
}

// --- Feedback loop ------------------------------------------------------

function askForFeedback() {
  state = "READY_FOR_FEEDBACK";
  appendBotMessage("One quick thing — was this explanation clear and actually useful?");
  appendQuickReplies([
    { label: "👍 Helpful", onClick: () => submitFeedback({ helpful: true, message: null }) },
    {
      label: "👎 Not helpful",
      onClick: () => {
        appendBotMessage("Sorry about that — what would've made this better?");
        appendQuickReplies([
          { label: "Skip", onClick: () => submitFeedback({ helpful: false, message: null }) },
        ]);
        state = "AWAITING_FEEDBACK_MSG";
      },
    },
  ]);
}

async function submitFeedback({ helpful, message }) {
  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ helpful, message, verdict_label: lastVerdictLabel }),
    });
  } catch (error) {
    // Feedback is a nice-to-have; never block the conversation if it fails.
    console.warn("Feedback submission failed:", error);
  }
  appendBotMessage("Thanks for letting me know! Paste another message or link anytime.");
  state = "AWAITING_SUBMISSION";
  lastVerdictLabel = null;
}

// --- Small helpers --------------------------------------------------------

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return escapeHTML(str).replaceAll('"', "&quot;");
}

greet();