// PCOS Symptom Check - form handling, validation, result rendering.
(function () {
  "use strict";

  var form = document.getElementById("form");
  var submit = document.getElementById("submit");
  var submitLabel = submit.querySelector(".submit-label");
  var spinner = submit.querySelector(".spinner");
  var formError = document.getElementById("formError");
  var result = document.getElementById("result");
  var bmiOut = document.getElementById("bmi_out");

  var card = document.getElementById("card");
  var formView = document.getElementById("formView");
  var resultView = document.getElementById("resultView");
  var aboutModal = document.getElementById("aboutModal");
  var outputModal = document.getElementById("outputModal");

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- keep the card + panes bounded to the space under the header, so a
  //     tall result scrolls inside the pane instead of clipping the card ---
  function syncCapHeight() {
    var appEl = document.querySelector(".app");
    if (appEl && appEl.clientHeight) {
      // +2px: clientHeight is rounded to an integer, so content sized from
      // fractional clamp()/vh values can come out a hair taller than the
      // measured cap and trip overflow-y:auto into showing a scrollbar for
      // content that otherwise fits. A couple of px of slack (silently
      // clipped by .shell's own overflow:hidden if ever unused) avoids that.
      document.documentElement.style.setProperty("--cap-h", (appEl.clientHeight + 2) + "px");
    }
  }
  syncCapHeight();
  window.addEventListener("load", syncCapHeight);
  window.addEventListener("resize", syncCapHeight);

  var NUMBER_FIELDS = {
    age: [12, 70, "age in years"],
    cycle_length: [0, 20, "period length in days"],
    height_cm: [120, 210, "height in centimetres"],
    weight_kg: [25, 200, "weight in kilograms"],
  };

  var BANDS = {
    lower: "That is about the same as everyone else in the data, so your answers do not stand out.",
    moderate: "That is above average, but not high enough to be sure either way.",
    higher: "That is well above average. Worth consulting a doctor. It is still not a diagnosis.",
  };

  // "What to do next" is written for the band this result actually landed
  // in, not hedged with "if your number is high" -- the number is already
  // known by the time this renders.
  var NEXT_STEPS = {
    lower: "Your answers do not match the usual PCOS pattern in this data. There is nothing urgent here, but mention any changes to your cycle or symptoms at your next checkup.",
    moderate: "Your answers sit in a grey area, neither clearly PCOS nor clearly not. Visit a qualified doctor, who can check with a scan and blood tests.",
    higher: "Your answers closely match the PCOS group in this data. Book a doctor's appointment. A scan and blood tests are the only way to confirm it.",
  };

  // --- live BMI ---------------------------------------------------
  function updateBmi() {
    var h = parseFloat(form.height_cm.value);
    var w = parseFloat(form.weight_kg.value);
    bmiOut.textContent =
      h > 0 && w > 0 ? (w / Math.pow(h / 100, 2)).toFixed(1) : "not yet calculated";
  }
  form.height_cm.addEventListener("input", updateBmi);
  form.weight_kg.addEventListener("input", updateBmi);

  // --- submit button doubles as a progress bar --------------------
  //     it fills left to right as the required answers are given, and
  //     turns solid white ("ready") once every one of them is valid.
  var REQUIRED_NUMS = ["age", "cycle_length", "height_cm", "weight_kg"];

  function formProgress() {
    var done = 0;
    REQUIRED_NUMS.forEach(function (name) {
      var spec = NUMBER_FIELDS[name];
      var raw = form[name].value.trim();
      var val = Number(raw);
      if (raw !== "" && !Number.isNaN(val) && val >= spec[0] && val <= spec[1]) done++;
    });
    if (form.cycle_irregular.value) done++;
    return done / (REQUIRED_NUMS.length + 1);
  }

  function updateProgress() {
    var p = formProgress();
    submit.style.setProperty("--progress", p.toFixed(3));
    submit.classList.toggle("is-ready", p >= 1);
  }

  form.addEventListener("input", updateProgress);
  form.addEventListener("change", updateProgress);
  updateProgress();

  // --- modals + view switching --------------------------------
  // closing a modal that holds zoom tiles (.anim-zoom) plays their
  // shrink-out first (.modal.closing, see style.css) before the dialog
  // itself actually closes, instead of the tiles just vanishing.
  function closeModal(modal) {
    if (!modal.close) { modal.removeAttribute("open"); return; }
    if (reduceMotion || !modal.querySelector(".anim-zoom")) { modal.close(); return; }
    modal.classList.add("closing");
    setTimeout(function () {
      modal.classList.remove("closing");
      modal.close();
    }, 160);
  }

  function wireModal(modal, openBtn) {
    if (!modal) return;
    if (openBtn) {
      openBtn.addEventListener("click", function () {
        if (modal.showModal) modal.showModal();
        else modal.setAttribute("open", "");
      });
    }
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal(modal);
    });
    modal.querySelectorAll("[data-close]").forEach(function (b) {
      b.addEventListener("click", function () { closeModal(modal); });
    });
  }
  wireModal(aboutModal, document.getElementById("openAbout"));
  wireModal(outputModal, document.getElementById("openOutputAbout"));

  // --- animate the card growing/shrinking when the view swaps --------
  //     height has no transform equivalent, so this is one of the few
  //     places we animate a layout property (see the animate skill's
  //     accordion exception). Width is measured too in case the two
  //     views ever use different card widths again.
  function animateCardResize(mutate) {
    if (!card) { mutate(); return; }
    var before = card.getBoundingClientRect();
    mutate();
    if (reduceMotion) return;

    var afterHeight = card.scrollHeight;
    var afterWidth = card.scrollWidth;
    if (Math.abs(afterHeight - before.height) < 1 && Math.abs(afterWidth - before.width) < 1) {
      return;
    }

    var ease = getComputedStyle(document.documentElement).getPropertyValue("--ease-out").trim() || "ease";

    card.style.height = before.height + "px";
    card.style.width = before.width + "px";
    card.style.overflow = "hidden";
    void card.offsetHeight; // force layout so the start size is committed

    card.style.transition = "height 0.42s " + ease + ", width 0.42s " + ease;
    card.style.height = afterHeight + "px";
    card.style.width = afterWidth + "px";

    var settled = false;
    function cleanup(e) {
      if (settled) return;
      if (e && e.target !== card) return;
      settled = true;
      card.removeEventListener("transitionend", cleanup);
      card.style.transition = "";
      card.style.height = "";
      card.style.width = "";
      card.style.overflow = "";
      syncCapHeight();
    }
    card.addEventListener("transitionend", cleanup);
    setTimeout(cleanup, 500); // safety net if transitionend never fires
  }

  function showResult() {
    animateCardResize(function () {
      formView.hidden = true;
      resultView.hidden = false;
      if (card) card.classList.add("result-mode");
    });
    if (card) card.scrollTop = 0;
    // on narrow screens the card no longer scrolls internally -- the whole
    // page does -- so resetting card.scrollTop alone leaves the new view
    // wherever the old one happened to be scrolled to.
    window.scrollTo(0, 0);
    syncCapHeight();
  }

  function showForm() {
    animateCardResize(function () {
      resultView.hidden = true;
      formView.hidden = false;
      if (card) card.classList.remove("result-mode");
    });
    result.innerHTML = "";
    form.reset();
    updateBmi();
    updateProgress();
    formError.hidden = true;
    formError.textContent = "";
    if (card) card.scrollTop = 0;
    window.scrollTo(0, 0);
    syncCapHeight();
  }

  document.getElementById("restart").addEventListener("click", showForm);

  // --- validation ----------------------------------------------
  function validate() {
    var problems = [];
    Object.keys(NUMBER_FIELDS).forEach(function (name) {
      var spec = NUMBER_FIELDS[name];
      var raw = form[name].value.trim();
      if (raw === "") {
        problems.push("Enter your " + spec[2] + ".");
        return;
      }
      var val = Number(raw);
      if (Number.isNaN(val)) {
        problems.push(spec[2] + " must be a number.");
      } else if (val < spec[0] || val > spec[1]) {
        problems.push(spec[2] + " should be between " + spec[0] + " and " + spec[1] + ".");
      }
    });
    if (!form.cycle_irregular.value) {
      problems.push("Choose whether your cycle is regular or irregular.");
    }
    return problems;
  }

  function collect() {
    var payload = {
      age: form.age.value,
      height_cm: form.height_cm.value,
      weight_kg: form.weight_kg.value,
      cycle_length: form.cycle_length.value,
      cycle_irregular: form.cycle_irregular.value,
    };
    ["weight_gain", "hair_growth", "skin_darkening", "hair_loss",
     "pimples", "fast_food", "regular_exercise"].forEach(function (name) {
      payload[name] = form[name].checked;
    });
    return payload;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // --- rendering ---------------------------------------------
  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function countPct(el, target) {
    if (reduceMotion) { el.textContent = target + "%"; return; }
    var start = performance.now();
    var duration = 900;
    (function frame(now) {
      var p = Math.min(1, (now - start) / duration);
      el.textContent = (p < 1 ? Math.round(target * easeOutCubic(p)) : target) + "%";
      if (p < 1) requestAnimationFrame(frame);
    })(start);
  }

  function bmiCategory(bmi) {
    if (bmi < 18.5) return "underweight";
    if (bmi < 25) return "healthy range";
    if (bmi < 30) return "overweight range";
    return "obese range";
  }

  function render(data) {
    var k = data.neighbours || 23;
    var mine = Math.round(data.percent);
    var base = data.baseline_percent || 33;
    var acc = data.model && data.model.accuracy
      ? Math.round(data.model.accuracy * 100)
      : 86;

    var factorsHtml;
    if (data.factors && data.factors.length) {
      factorsHtml =
        '<div class="factors rblock anim" style="--i:2">' +
          '<span class="rlabel">What you reported</span>' +
          "<ul>" +
          data.factors.slice(0, 3).map(function (f) {
            return '<li><span class="f-name">' + escapeHtml(f.label) + "</span>" +
                   '<span class="f-lift">' + f.lift.toFixed(1) +
                   "x more common in PCOS</span></li>";
          }).join("") +
          "</ul>" +
          '<p class="fnote">These signs show up more often in people who have PCOS. ' +
          "They are clues, not causes.</p>" +
        "</div>";
    } else {
      factorsHtml =
        '<div class="factors rblock anim" style="--i:2">' +
          '<span class="rlabel">What you reported</span>' +
          '<p class="none">None of your answers are strongly linked to PCOS in ' +
          "this data.</p>" +
        "</div>";
    }

    var bmiHtml = "";
    if (data.bmi) {
      var bmiNote = data.bmi >= 25
        ? "A higher BMI is linked to PCOS in this data."
        : "BMI is one of the 13 answers the estimate uses.";
      bmiHtml =
        '<div class="rblock anim" style="--i:3">' +
          '<span class="rlabel">Your body mass index</span>' +
          '<p class="bmi-read"><b>' + data.bmi.toFixed(1) + "</b> " +
            '<span class="bmi-cat">' + bmiCategory(data.bmi) + "</span></p>" +
          '<p class="fnote">' + bmiNote + "</p>" +
        "</div>";
    }

    var hero =
      '<div class="hero anim" style="--i:0">' +
        '<div class="score">' +
          '<span class="pct">0%</span>' +
          '<span class="badge ' + data.band + '">' + data.band + "</span>" +
        "</div>" +
        '<div class="meter-wrap">' +
          '<div class="meter"><i id="meterFill"></i></div>' +
          '<span class="meter-mark" style="--at:' + base + '%"></span>' +
        "</div>" +
        '<div class="meter-scale">' +
          '<span class="lo">0%</span>' +
          '<span class="avg" style="--at:' + base + '%">avg ' + base + '%</span>' +
          '<span class="hi">100%</span>' +
        "</div>" +
        '<p class="interp"><b>Of the ' + k + " people in our data most like you, " +
          data.percent + "% had PCOS.</b> " + BANDS[data.band] + "</p>" +
      "</div>";

    var compareHtml =
      '<div class="rblock anim" style="--i:2">' +
        '<span class="rlabel">Compared with everyone else</span>' +
        '<div class="compare">' +
          '<div class="cmp-row">' +
            '<span class="cmp-label">Everyone in the data</span>' +
            '<span class="cmp-val">' + base + " in 100</span>" +
            '<span class="cmp-bar"><i style="--w:' + base + '%"></i></span>' +
          "</div>" +
          '<div class="cmp-row mine">' +
            '<span class="cmp-label">People most like you</span>' +
            '<span class="cmp-val">' + mine + " in 100</span>" +
            '<span class="cmp-bar"><i style="--w:' + Math.max(2, mine) + '%"></i></span>' +
          "</div>" +
        "</div>" +
      "</div>";

    var nextHtml =
      '<div class="rblock anim" style="--i:3">' +
        '<span class="rlabel">What to do next</span>' +
        "<p>" + NEXT_STEPS[data.band] + " In testing, this method was right " +
        acc + " times out of 100.</p>" +
      "</div>";

    var colA = '<div class="col-a">' + compareHtml + nextHtml + "</div>";
    var colB = '<div class="col-b">' + factorsHtml + bmiHtml + "</div>";

    result.innerHTML = '<div class="shown">' + hero + colA + colB + "</div>";

    requestAnimationFrame(function () {
      var fill = document.getElementById("meterFill");
      if (fill) fill.style.transform = "scaleX(" + Math.max(0.02, data.percent / 100) + ")";
      var pct = result.querySelector(".pct");
      if (pct) countPct(pct, data.percent);
      syncCapHeight();
    });
  }

  // --- submit -----------------------------------------------
  var busy = false;

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (busy) return;

    formError.hidden = true;
    formError.textContent = "";

    var problems = validate();
    if (problems.length) {
      formError.innerHTML = problems.length === 1
        ? escapeHtml(problems[0])
        : problems.map(escapeHtml).join("<br>");
      formError.hidden = false;
      return;
    }

    busy = true;
    submit.disabled = true;
    submit.classList.add("is-busy");
    spinner.hidden = false;
    submitLabel.textContent = "Checking";

    fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collect()),
    })
      .then(function (res) {
        return res.json().then(function (body) {
          if (!res.ok) throw new Error(body.error || "Something went wrong. Please try again.");
          return body;
        });
      })
      .then(function (data) {
        render(data);
        showResult();
      })
      .catch(function (err) {
        formError.textContent = err.message;
        formError.hidden = false;
      })
      .finally(function () {
        busy = false;
        submit.disabled = false;
        submit.classList.remove("is-busy");
        spinner.hidden = true;
        submitLabel.textContent = "Check my result";
      });
  });
})();
