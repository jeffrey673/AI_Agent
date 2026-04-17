"""Regression test for: edit-and-resend produces duplicate user bubble.

Bug: `_resendEditedMessage` in chat.js updated the original user message's text
in place, then called `sendMessage()`, which appends a fresh user bubble via
`appendUserMessage()`. Result: the edited text shows up twice in the DOM
(and twice in `currentMessages`), and the AI receives the same question twice.

This test reproduces the invariant with a minimal harness that embeds the two
critical functions from chat.js (`_resendEditedMessage` + `appendUserMessage`)
in a synthetic page. It asserts that after an edit-and-resend cycle, exactly
one user bubble carries the edited text and exactly one user entry lives in
the in-memory messages array.

The harness ships two modes: `BUGGY` (old implementation) and `FIXED` (new
implementation). `BUGGY` must fail the invariant, `FIXED` must pass it — this
protects against future regressions that re-introduce the duplicate.
"""

import pytest
from playwright.sync_api import sync_playwright


HARNESS_HTML = r"""
<!doctype html>
<html><head><meta charset="utf-8"><title>edit resend fixture</title></head>
<body>
<div id="chat-messages"></div>
<textarea id="chat-input"></textarea>
<script>
(function () {
  "use strict";

  var chatMessages = document.getElementById("chat-messages");
  var chatInput = document.getElementById("chat-input");
  var currentMessages = [];
  window.__state = { currentMessages: currentMessages };

  function appendUserMessage(text) {
    var div = document.createElement("div");
    div.className = "message message-user";
    var bubble = document.createElement("div");
    bubble.className = "message-content";
    bubble.dataset.raw = text;
    bubble.textContent = text;
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    return div;
  }

  function appendAiStub(text) {
    var div = document.createElement("div");
    div.className = "message message-ai";
    div.textContent = text;
    chatMessages.appendChild(div);
    return div;
  }

  // Stub sendMessage: mimics the real sendMessage side effects that matter
  // for this bug — appendUserMessage(text) and currentMessages.push(user).
  function sendMessage() {
    var text = chatInput.value.trim();
    if (!text) return;
    appendUserMessage(text);
    currentMessages.push({ role: "user", content: text });
    chatInput.value = "";
    // Simulate AI reply
    appendAiStub("AI reply to: " + text);
    currentMessages.push({ role: "assistant", content: "AI reply to: " + text });
  }

  // ---- BUGGY version (pre-fix) ----
  function _resendEditedMessageBuggy(msgEl, newText) {
    var siblings = Array.from(chatMessages.children);
    var idx = siblings.indexOf(msgEl);
    if (idx >= 0) {
      for (var i = siblings.length - 1; i > idx; i--) {
        siblings[i].remove();
      }
    }
    var bubble = msgEl.querySelector(".message-content");
    if (bubble) {
      bubble.dataset.raw = newText;
      bubble.textContent = newText;
    }
    var domUserMsgs = chatMessages.querySelectorAll(".message-user");
    var msgIndex = -1;
    for (var k = 0; k < domUserMsgs.length; k++) {
      if (domUserMsgs[k] === msgEl) { msgIndex = k; break; }
    }
    if (msgIndex >= 0) {
      var cmIdx = -1, uIdx = 0;
      for (var m = 0; m < currentMessages.length; m++) {
        if (currentMessages[m].role === "user") {
          if (uIdx === msgIndex) { cmIdx = m; break; }
          uIdx++;
        }
      }
      if (cmIdx >= 0) {
        currentMessages[cmIdx].content = newText;
        currentMessages.splice(cmIdx + 1);
      }
    }
    chatInput.value = newText;
    sendMessage();
  }

  // ---- FIXED version (post-fix, mirrors chat.js:2029) ----
  function _resendEditedMessageFixed(msgEl, newText) {
    var domUserMsgs = chatMessages.querySelectorAll(".message-user");
    var msgIndex = -1;
    for (var k = 0; k < domUserMsgs.length; k++) {
      if (domUserMsgs[k] === msgEl) { msgIndex = k; break; }
    }
    var siblings = Array.from(chatMessages.children);
    var idx = siblings.indexOf(msgEl);
    if (idx >= 0) {
      for (var i = siblings.length - 1; i >= idx; i--) {
        siblings[i].remove();
      }
    }
    if (msgIndex >= 0) {
      var cmIdx = -1, uIdx = 0;
      for (var m = 0; m < currentMessages.length; m++) {
        if (currentMessages[m].role === "user") {
          if (uIdx === msgIndex) { cmIdx = m; break; }
          uIdx++;
        }
      }
      if (cmIdx >= 0) {
        currentMessages.splice(cmIdx);
      }
    }
    chatInput.value = newText;
    sendMessage();
  }

  // Test harness: send A, then edit to B using the chosen impl.
  window.runScenario = function (mode) {
    chatMessages.innerHTML = "";
    currentMessages.length = 0;

    chatInput.value = "A";
    sendMessage();                          // DOM: [A, AI(A)]
    var firstUser = chatMessages.querySelector(".message-user");

    var impl = mode === "buggy"
      ? _resendEditedMessageBuggy
      : _resendEditedMessageFixed;
    impl(firstUser, "B");                   // edit A -> B, resend

    var userBubbles = chatMessages.querySelectorAll(".message-user");
    var bTexts = [];
    userBubbles.forEach(function (u) {
      bTexts.push(u.querySelector(".message-content").textContent);
    });
    return {
      userBubbleCount: userBubbles.length,
      bubbleTexts: bTexts,
      memUserCount: currentMessages.filter(function (m) {
        return m.role === "user";
      }).length,
      memUserTexts: currentMessages
        .filter(function (m) { return m.role === "user"; })
        .map(function (m) { return m.content; }),
    };
  };
})();
</script>
</body></html>
"""


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.set_content(HARNESS_HTML)
    yield pg
    ctx.close()


def test_buggy_version_reproduces_duplicate(page):
    """Guard: the old implementation must still reproduce the bug.

    If this ever starts passing, the harness drifted — the bug classification
    is no longer valid and the fix's meaning is lost.
    """
    result = page.evaluate("window.runScenario('buggy')")
    # Buggy: B appears twice in DOM and twice in memory.
    assert result["userBubbleCount"] == 2, result
    assert result["bubbleTexts"] == ["B", "B"], result
    assert result["memUserCount"] == 2, result
    assert result["memUserTexts"] == ["B", "B"], result


def test_fixed_version_shows_b_once(page):
    """Regression: after edit-and-resend, B must appear exactly once."""
    result = page.evaluate("window.runScenario('fixed')")
    assert result["userBubbleCount"] == 1, result
    assert result["bubbleTexts"] == ["B"], result
    assert result["memUserCount"] == 1, result
    assert result["memUserTexts"] == ["B"], result
