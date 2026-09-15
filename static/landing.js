/* Intelligence Designed To Evolve - landing interactions */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------
     Stat count-up  (easeOutCubic, once, IntersectionObserver 0.25)
     --------------------------------------------------------------- */
  var values = Array.prototype.slice.call(document.querySelectorAll(".stat-value"));

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function format(value, decimals) {
    return value.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  function countUp(el, index) {
    var target = parseFloat(el.dataset.target);
    var decimals = parseInt(el.dataset.decimals || "0", 10);
    var suffix = el.dataset.suffix || "";

    if (reduceMotion || !isFinite(target)) {
      el.textContent = format(target, decimals) + suffix;
      return;
    }

    var duration = 1500 + index * 80;
    var startDelay = 480 + index * 90;

    window.setTimeout(function () {
      var start = performance.now();

      function frame(now) {
        var p = Math.min(1, (now - start) / duration);
        el.textContent = format(target * easeOutCubic(p), decimals) + suffix;
        if (p < 1) {
          requestAnimationFrame(frame);
        } else {
          el.textContent = format(target, decimals) + suffix;
        }
      }

      requestAnimationFrame(frame);
    }, startDelay);
  }

  function runAll() {
    values.forEach(countUp);
  }

  if (values.length) {
    var statsEl = document.querySelector(".stats");
    if (reduceMotion || !("IntersectionObserver" in window) || !statsEl) {
      runAll();
    } else {
      var fired = false;
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting && !fired) {
              fired = true;
              runAll();
              observer.disconnect();
            }
          });
        },
        { threshold: 0.25 }
      );
      observer.observe(statsEl);
    }
  }

  /* ---------------------------------------------------------------
     Mobile only: leaving the landing page for /app or /data. On a
     mobile viewport the nav sits visibly lower here than on the next
     page -- .page centers the whole header/hero/stats group on short
     screens, so the nav isn't pinned to the top the way it is on
     /app and /data. Animate it up into that "top of screen" position
     first (fading the rest of the page out with it), then navigate --
     so it reads as the nav settling into place before the new page's
     own content fades in top-to-bottom, instead of the nav visibly
     jumping between two different spots across the page load.
     Not for /app <-> /data: both are already top-pinned, nothing to
     settle into. This file is shared, so guard on .hero (landing-only).
     --------------------------------------------------------------- */
  var isLanding = !!document.querySelector(".hero");
  var headerEl = document.querySelector(".header");
  if (isLanding && headerEl && !reduceMotion) {
    var mobileNav = window.matchMedia("(max-width: 720px)");
    var leaving = false;
    document.querySelectorAll(".nav-link, .cta").forEach(function (link) {
      link.addEventListener("click", function (e) {
        if (leaving || !mobileNav.matches) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
        var href = link.getAttribute("href") || "";
        if (href !== "/app" && href !== "/data") return;

        e.preventDefault();
        leaving = true;

        // .header's own entrance (navSlideDown, fill-mode "both") never
        // lets go of `transform`/`opacity` once it's run -- a CSS
        // animation holds higher cascade priority than a plain inline
        // style for as long as it's still applied, so setting
        // style.transform below would otherwise be silently ignored and
        // the header just wouldn't move at all (which is exactly why it
        // looked like a teleport: nothing happened for 380ms, then the
        // next page loaded already in its different spot). Cancel the
        // animation to free those properties up -- but .header's own
        // base rule declares a static opacity: 0 (the animation was the
        // only thing ever pushing it to 1), so cancelling it without
        // also setting opacity back snaps the header invisible instead.
        // Force a reflow so the removal is committed before the
        // transition and new values are applied, or the browser can
        // coalesce them into one style recalc and skip the transition.
        headerEl.style.animation = "none";
        headerEl.style.opacity = "1";
        void headerEl.offsetHeight;

        // /app and /data's .shell pads clamp(12px, 1.8vh, 20px) above the
        // nav -- 12px is the floor of that, it can't go lower on any
        // device. Deliberately overshoot past even that -- past the
        // literal top edge (0) and slightly off-screen: the destination's
        // own entrance animation is already suppressed for this
        // navigation, so the settle down to its real ~12-20px resting
        // spot when the new page paints reads as the nav finishing its
        // landing, not a second jump.
        var targetTop = -5;

        var delta = targetTop - headerEl.getBoundingClientRect().top;
        headerEl.style.transition = "transform 0.38s cubic-bezier(0.22, 1, 0.36, 1)";
        headerEl.style.transform = "translateY(" + delta + "px)";

        document.querySelectorAll(".hero, .stats").forEach(function (el) {
          el.style.transition = "opacity 0.3s ease";
          el.style.opacity = "0";
        });

        window.setTimeout(function () { window.location.href = href; }, 380);
      });
    });
  }

  /* ---------------------------------------------------------------
     Mobile only, the reverse trip: leaving /app or /data for the
     landing page (tapping "Home"). This time the content leaves
     first, then the nav glides back down to where it started --
     opposite order from the up-trip, where the nav moved first and
     the content faded with it. Landing's own entrance animation is
     NOT suppressed for this arrival (unlike /app <-> /data), so it
     plays normally on top of this and settles into its real position
     regardless of exactly where this glide ends.
     --------------------------------------------------------------- */
  if (!isLanding && headerEl && !reduceMotion) {
    var mobileNavBack = window.matchMedia("(max-width: 720px)");
    var leavingBack = false;
    document.querySelectorAll(".nav-link").forEach(function (link) {
      link.addEventListener("click", function (e) {
        if (leavingBack || !mobileNavBack.matches) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
        if ((link.getAttribute("href") || "") !== "/") return;

        e.preventDefault();
        leavingBack = true;

        var href = "/";
        var content = document.querySelector(".app, .doc");
        if (content) {
          content.style.transition = "opacity 0.25s ease";
          content.style.opacity = "0";
        }

        window.setTimeout(function () {
          // same reasoning as the up-trip: cancel navSlideDown (it holds
          // transform/opacity for good once it's run) before driving the
          // header with our own transform, and re-assert opacity since
          // the animation was the only thing keeping it at 1.
          headerEl.style.animation = "none";
          headerEl.style.opacity = "1";
          void headerEl.offsetHeight;
          headerEl.style.transition = "transform 0.35s cubic-bezier(0.22, 1, 0.36, 1)";
          headerEl.style.transform = "translateY(75px)";

          window.setTimeout(function () { window.location.href = href; }, 350);
        }, 250);
      });
    });
  }

  /* ---------------------------------------------------------------
     Nudge the background video to play (autoplay + muted should be
     enough, but some browsers need the explicit call)
     --------------------------------------------------------------- */
  var video = document.querySelector(".bg-video");
  if (video) {
    var playPromise = video.play();
    if (playPromise && typeof playPromise.catch === "function") {
      playPromise.catch(function () {
        // autoplay blocked at the OS/browser level (e.g. iOS Low Power
        // Mode disables it even for muted video, regardless of the
        // playsinline/autoplay attributes) -- the video would otherwise
        // sit there showing its native "tap to play" overlay forever,
        // unclickable, since .bg-video is deliberately pointer-events:
        // none (taps need to pass through to the nav/content on top of
        // it). .bg's own dark gradient wash already looks intentional
        // without the video, so just hide it instead.
        video.style.display = "none";
      });
    }
  }
})();
