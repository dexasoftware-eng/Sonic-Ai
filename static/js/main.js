
(function () {
  "use strict";

  if (typeof gsap !== "undefined" && typeof ScrollTrigger !== "undefined") {
    gsap.registerPlugin(ScrollTrigger);
  }

  /* -------- Lenis smooth scroll -------- */
  var lenis = null;
  try {
    if (typeof Lenis !== "undefined") {
      lenis = new Lenis({ lerp: 0.11, smoothWheel: true });
      if (typeof ScrollTrigger !== "undefined") {
        lenis.on("scroll", ScrollTrigger.update);
      }
      gsap.ticker.add(function (time) {
        lenis.raf(time * 1000);
      });
      gsap.ticker.lagSmoothing(0);
    }
  } catch (e) {
    console.warn("Lenis scroll initialization skipped:", e);
  }

  /* -------- Anchor smooth scroll -------- */
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      var id = a.getAttribute("href");
      if (!id || id.length < 2) return;
      var target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      closeMobileNav();
      if (lenis) {
        lenis.scrollTo(target, { offset: -70 });
      } else {
        target.scrollIntoView({ behavior: "smooth" });
      }
    });
  });

  /* -------- Mobile nav toggle -------- */
  var mobileNav = document.getElementById("mobileNav");
  var burgerBtn = document.getElementById("burgerBtn");
  var mobileNavClose = document.getElementById("mobileNavClose");

  function openMobileNav() {
    if (mobileNav) mobileNav.classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeMobileNav() {
    if (mobileNav) mobileNav.classList.remove("open");
    document.body.style.overflow = "";
  }

  if (burgerBtn) burgerBtn.addEventListener("click", openMobileNav);
  if (mobileNavClose) mobileNavClose.addEventListener("click", closeMobileNav);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeMobileNav();
  });

  /* -------- Scroll progress bar -------- */
  if (document.getElementById("scrollBar") && typeof gsap !== "undefined") {
    gsap.to("#scrollBar", {
      scaleX: 1,
      ease: "none",
      scrollTrigger: {
        trigger: document.body,
        start: "top top",
        end: "bottom bottom",
        scrub: 0.3,
      },
    });
  }

  /* -------- Nav state: transparent on hero -> frosted solid on scroll -------- */
  var nav = document.getElementById("nav");
  if (nav && typeof ScrollTrigger !== "undefined") {
    ScrollTrigger.create({
      start: "top -50",
      end: 999999,
      toggleClass: { targets: nav, className: "scrolled" },
    });

    var heroPhoto = document.getElementById("heroPhoto");
    if (heroPhoto) {
      ScrollTrigger.create({
        trigger: "#heroPhoto",
        start: "top top",
        end: "bottom 10%",
        onLeave: function () {
          nav.classList.remove("on-dark");
        },
        onEnterBack: function () {
          nav.classList.add("on-dark");
        },
      });
    }
  }

  /* -------- Hero subtle parallax / ken-burns -------- */
  var heroArt = document.getElementById("heroPhotoArt");
  if (heroArt && typeof gsap !== "undefined") {
    gsap.to("#heroPhotoArt", {
      scale: 1.14,
      ease: "none",
      scrollTrigger: {
        trigger: "#heroPhoto",
        start: "top top",
        end: "bottom top",
        scrub: true,
      },
    });
  }

  /* -------- Waveform builder helper -------- */
  function buildWave(container, count, minPct, maxPct) {
    var bars = [];
    container.innerHTML = "";
    for (var i = 0; i < count; i++) {
      var b = document.createElement("span");
      container.appendChild(b);
      bars.push(b);
    }
    return bars;
  }

  function loopWaveform(bars, minH, maxH, speed) {
    if (!bars || !bars.length) return;
    gsap.to(bars, {
      height: function () {
        return minH + Math.random() * (maxH - minH) + "%";
      },
      duration: speed,
      ease: "sine.inOut",
      stagger: { each: 0.008, from: "random" },
      onComplete: function () {
        loopWaveform(bars, minH, maxH, speed);
      },
    });
  }

  /* -------- Hero HUD Live Waveform Animation -------- */
  var heroWaveEl = document.getElementById("heroWaveVisualizer") || document.getElementById("aboutWaveVisualizer");
  if (heroWaveEl && typeof gsap !== "undefined") {
    var heroBars = buildWave(heroWaveEl, 36, 12, 95);
    loopWaveform(heroBars, 15, 95, 0.45);
  }

  /* -------- Hero HUD Live Telemetry Simulator -------- */
  var hudDbTag = document.getElementById("hudDbTag");
  if (hudDbTag) {
    var dbs = [-14.2, -13.8, -15.1, -12.9, -14.6, -13.4, -16.0];
    setInterval(function () {
      var randDb = dbs[Math.floor(Math.random() * dbs.length)];
      hudDbTag.textContent = randDb.toFixed(1) + " dBFS Peak";
    }, 2200);
  }

  /* -------- Problem Section Mock Waveform -------- */
  var mockWaveEl = document.getElementById("mockWaveA");
  if (mockWaveEl && typeof gsap !== "undefined") {
    var waveA = buildWave(mockWaveEl, 38, 10, 80);
    ScrollTrigger.create({
      trigger: "#mockWaveA",
      start: "top 85%",
      once: true,
      onEnter: function () {
        gsap.to(waveA, {
          height: function () {
            return 12 + Math.random() * 80 + "%";
          },
          duration: 1,
          ease: "power3.out",
          stagger: { each: 0.006, from: "center" },
          onComplete: function () {
            loopWaveform(waveA, 10, 85, 1.4);
          },
        });

        var gaugeRing = document.getElementById("gaugeRingA");
        if (gaugeRing) {
          gsap.to("#gaugeRingA", {
            "--pct": 96,
            duration: 1.3,
            ease: "power3.out",
            onUpdate: function () {
              var v = gsap.getProperty("#gaugeRingA", "--pct");
              var gaugeNum = document.getElementById("gaugeNumA");
              if (gaugeNum) gaugeNum.textContent = Math.round(v) + "%";
            },
          });
        }

        document
          .querySelectorAll(".split-media .mock-row-fill")
          .forEach(function (f) {
            var val = f.getAttribute("data-value") || "0";
            gsap.to(f, { width: val + "%", duration: 1.1, ease: "power3.out" });
          });
      },
    });
  }

  /* -------- Marquee: duplicate track for seamless loop -------- */
  var track = document.getElementById("stripTrack");
  if (track && !track.dataset.duplicated) {
    track.innerHTML += track.innerHTML;
    track.dataset.duplicated = "true";
  }

  /* -------- Hero Entrance Animations -------- */
  if (typeof gsap !== "undefined") {
    var heroTl = gsap.timeline({ delay: 0.1 });
    heroTl
      .from(".hero-status-pill", {
        opacity: 0,
        y: 16,
        duration: 0.6,
        ease: "power2.out",
      })
      .from(
        ".hero h1",
        { opacity: 0, y: 24, duration: 0.8, ease: "power3.out" },
        "-=0.4",
      )
      .from(
        ".hero-sub",
        { opacity: 0, y: 16, duration: 0.7, ease: "power2.out" },
        "-=0.5",
      )
      .from(
        ".hero-actions .btn",
        { opacity: 0, y: 12, duration: 0.5, stagger: 0.08, ease: "power2.out" },
        "-=0.4",
      )
      .from(
        ".hero-metrics",
        { opacity: 0, y: 14, duration: 0.6, ease: "power2.out" },
        "-=0.3",
      )
      .from(
        ".hero-hud",
        { opacity: 0, scale: 0.95, y: 20, duration: 0.8, ease: "power3.out" },
        "-=0.6",
      );

    /* -------- Generic reveal animations -------- */
    document.querySelectorAll(".reveal").forEach(function (el) {
      gsap.to(el, {
        opacity: 1,
        y: 0,
        duration: 0.85,
        ease: "power2.out",
        scrollTrigger: { trigger: el, start: "top 85%", once: true },
      });
    });

    /* -------- Process cards stagger -------- */
    if (document.querySelector(".proc-grid")) {
      gsap.from(".proc-card", {
        opacity: 0,
        y: 24,
        duration: 0.65,
        ease: "power2.out",
        stagger: 0.1,
        scrollTrigger: { trigger: ".proc-grid", start: "top 82%", once: true },
      });
    }

    /* -------- Category items stagger -------- */
    if (document.querySelector(".cat-row")) {
      gsap.from(".cat", {
        opacity: 0,
        y: 16,
        duration: 0.5,
        ease: "power2.out",
        stagger: { each: 0.04, from: "start" },
        scrollTrigger: { trigger: ".cat-row", start: "top 85%", once: true },
      });
    }

    /* -------- Capability cards stagger -------- */
    if (document.querySelector(".cap-grid")) {
      gsap.from(".cap-card", {
        opacity: 0,
        y: 20,
        duration: 0.6,
        ease: "power2.out",
        stagger: 0.08,
        scrollTrigger: { trigger: ".cap-grid", start: "top 85%", once: true },
      });
    }

    /* -------- Role rows stagger -------- */
    if (document.querySelector(".ind-list")) {
      gsap.from(".ind-row", {
        opacity: 0,
        x: -16,
        duration: 0.55,
        ease: "power2.out",
        stagger: 0.08,
        scrollTrigger: { trigger: ".ind-list", start: "top 85%", once: true },
      });
    }

    /* -------- Stat counters -------- */
    document.querySelectorAll(".count").forEach(function (el) {
      var target = parseFloat(el.getAttribute("data-target"));
      if (isNaN(target)) return;
      var obj = { val: 0 };
      ScrollTrigger.create({
        trigger: el,
        start: "top 90%",
        once: true,
        onEnter: function () {
          gsap.to(obj, {
            val: target,
            duration: 1.6,
            ease: "power2.out",
            onUpdate: function () {
              el.textContent = Math.round(obj.val).toLocaleString();
            },
          });
        },
      });
    });
  }

  /* -------- Roles caption rotator -------- */
  var indScenes = [
    {
      title: "Loading Dock · Camera 03",
      desc: "Glass Breaking detected at 94% — High severity, escalated to Security Operator.",
    },
    {
      title: "Warehouse Floor · Mic 12",
      desc: "Machinery Fault confirmed after repeat detection — inspection recommended.",
    },
    {
      title: "Lobby · Camera 01",
      desc: "Person Asking for Help detected — Critical alert, routed to Security Operator.",
    },
  ];
  
  var indIdx = 0;
  var indTitle = document.getElementById("indCapTitle");
  var indDesc = document.getElementById("indCapDesc");
  var indDots = document.getElementById("indDots")
    ? document.getElementById("indDots").children
    : [];

  if (indTitle && indDesc && indScenes.length > 0) {
    setInterval(function () {
      indIdx = (indIdx + 1) % indScenes.length;
      if (typeof gsap !== "undefined") {
        gsap.to([indTitle, indDesc], {
          opacity: 0,
          duration: 0.25,
          onComplete: function () {
            indTitle.textContent = indScenes[indIdx].title;
            indDesc.textContent = indScenes[indIdx].desc;
            gsap.to([indTitle, indDesc], { opacity: 1, duration: 0.35 });
          },
        });
      } else {
        indTitle.textContent = indScenes[indIdx].title;
        indDesc.textContent = indScenes[indIdx].desc;
      }
      Array.prototype.forEach.call(indDots, function (d, i) {
        d.classList.toggle("active", i === indIdx);
      });
    }, 3600);
  }

  /* -------- FAQ accordion -------- */
  document.querySelectorAll(".faq-item").forEach(function (item) {
    var btn = item.querySelector(".faq-q");
    if (btn) {
      btn.addEventListener("click", function () {
        var wasOpen = item.classList.contains("open");
        document.querySelectorAll(".faq-item.open").forEach(function (o) {
          o.classList.remove("open");
        });
        if (!wasOpen) item.classList.add("open");
      });
    }
  });

  if (typeof ScrollTrigger !== "undefined") {
    ScrollTrigger.refresh();
  }
})();
