/* SKIN1004 AI — auth.js
   Login / Signup form handling
*/

(function () {
  "use strict";

  var form = document.getElementById("auth-form");
  var nameGroup = document.getElementById("name-group");
  var nameInput = document.getElementById("input-name");
  var emailInput = document.getElementById("input-email");
  var passwordInput = document.getElementById("input-password");
  var submitBtn = document.getElementById("btn-submit");
  var toggleLink = document.getElementById("toggle-link");
  var errorMsg = document.getElementById("error-msg");
  var formTitle = document.getElementById("form-title");

  var isSignup = false;

  function setMode(signup) {
    isSignup = signup;
    if (signup) {
      nameGroup.style.display = "block";
      submitBtn.textContent = "SIGN UP";
      toggleLink.textContent = "Already have an account? Sign in";
      formTitle.textContent = "Create Account";
    } else {
      nameGroup.style.display = "none";
      submitBtn.textContent = "SIGN IN";
      toggleLink.textContent = "Need an account? Sign up";
      formTitle.textContent = "Welcome Back";
    }
    errorMsg.textContent = "";
  }

  toggleLink.addEventListener("click", function () {
    setMode(!isSignup);
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    errorMsg.textContent = "";
    submitBtn.disabled = true;

    var url = isSignup ? "/api/auth/signup" : "/api/auth/signin";
    var body = {
      email: emailInput.value.trim(),
      password: passwordInput.value,
    };

    if (isSignup) {
      body.name = nameInput.value.trim();
      if (!body.name) {
        errorMsg.textContent = "Name is required";
        submitBtn.disabled = false;
        return;
      }
    }

    if (!body.email) {
      errorMsg.textContent = "Email is required";
      submitBtn.disabled = false;
      return;
    }

    if (!body.password || body.password.length < 4) {
      errorMsg.textContent = "Password must be at least 4 characters";
      submitBtn.disabled = false;
      return;
    }

    try {
      var resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (resp.ok) {
        window.location.href = "/";
      } else {
        var data = await resp.json().catch(function () { return {}; });
        errorMsg.textContent = data.detail || "Authentication failed";
      }
    } catch (err) {
      errorMsg.textContent = "Network error. Please try again.";
    }

    submitBtn.disabled = false;
  });

  // Initialize
  setMode(false);
})();
