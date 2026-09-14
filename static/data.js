// /data page - reading progress bar, scroll-triggered card reveal, and
// (mobile) a glow on whichever section is currently in view.
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- reading progress bar ----------------------------------------
  var fill = document.getElementById("scrollFill");
  var ticking = false;
  function updateProgress() {
    ticking = false;
    var doc = document.documentElement;
    var max = doc.scrollHeight - doc.clientHeight;
    var p = max > 0 ? Math.min(1, Math.max(0, doc.scrollTop / max)) : 0;
    if (fill) fill.style.transform = "scaleX(" + p.toFixed(4) + ")";
    checkBottom(max, doc.scrollTop);
  }
  window.addEventListener("scroll", function () {
    if (!ticking) {
      requestAnimationFrame(updateProgress);
      ticking = true;
    }
  }, { passive: true });

  // --- entrance: above the fold syncs with the nav, below it reveals
  //     on scroll ----------------------------------------------------
  //     Whatever's already in the viewport at load (the intro, maybe the
  //     first card) used to wait on an IntersectionObserver callback --
  //     asynchronous and untimed -- while the nav animates in on a fixed
  //     CSS delay. That gap is what made the nav and the page content
  //     look like two unrelated things arriving separately, instead of
  //     the "content unfurls out of the nav" feel every other page has.
  //     Fix: anything already visible switches to the same .anim class
  //     (and delay cadence) the nav and every other page's content use,
  //     so it's genuinely the same synchronised entrance, not scroll-
  //     reveal that merely fires fast. Only what's actually off-screen
  //     stays on the scroll-triggered .reveal system.
  var revealEls = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
  if (!reduceMotion && revealEls.length) {
    var vh = window.innerHeight || document.documentElement.clientHeight;
    var immediate = [];
    var deferred = [];
    revealEls.forEach(function (el) {
      (el.getBoundingClientRect().top < vh * 0.92 ? immediate : deferred).push(el);
    });

    immediate.forEach(function (el, i) {
      el.classList.remove("reveal");
      el.classList.add("anim");
      el.style.setProperty("--d", (0.06 + i * 0.08) + "s");
    });

    if ("IntersectionObserver" in window && deferred.length) {
      document.documentElement.classList.add("js-reveal-ready");
      var revealObserver = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              // a CSS transition-delay (not setTimeout) so the stagger is
              // paced by the compositor, not the JS main thread --
              // setTimeout can drift under any load and read as an
              // inconsistent gap between cards instead of an even cascade.
              var idx = deferred.indexOf(entry.target);
              var delay = Math.min(Math.max(idx, 0) * 90, 270);
              entry.target.style.transitionDelay = delay + "ms";
              entry.target.classList.add("is-visible");
              revealObserver.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
      );
      deferred.forEach(function (el) { revealObserver.observe(el); });
    }
  }

  // --- mobile glow: highlight whichever section is in view -----------
  //     (.doc-card.is-current, style.css -- the same glow the "ready"
  //     submit button uses; desktop gets the equivalent as a hover
  //     animation instead, so this only visibly does anything on mobile)
  var sections = Array.prototype.slice.call(document.querySelectorAll(".doc-card[id]"));

  if (sections.length && "IntersectionObserver" in window) {
    var tocObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var id = entry.target.id;
          sections.forEach(function (s) {
            s.classList.toggle("is-current", s.id === id);
          });
        });
      },
      { rootMargin: "-45% 0px -50% 0px", threshold: 0 }
    );
    sections.forEach(function (s) { tocObserver.observe(s); });
  }

  // the "-45%/-50%" band above never gets crossed by the last section once
  // the page hits max scroll (it can't be pushed further up into the mid-
  // viewport band), so force the last one current once you hit the bottom.
  function checkBottom(max, scrollTop) {
    if (!sections.length) return;
    if (max > 0 && max - scrollTop < 4) {
      sections.forEach(function (s, i) {
        s.classList.toggle("is-current", i === sections.length - 1);
      });
    }
  }

  updateProgress();
})();
