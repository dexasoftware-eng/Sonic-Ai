let smoother = null;

const internalLinks = document.querySelectorAll('a[href^="#"]');

internalLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    const targetId = link.getAttribute("href");
    if (!targetId || targetId === "#") return;

    const target = document.querySelector(targetId);
    if (!target) return;

    event.preventDefault();

    if (smoother) {
      smoother.scrollTo(target, true, "top top");
    } else {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  /*
    ScrollSmoother transforms #smooth-content.
    Keep the fullscreen fixed mobile menu outside that transformed tree.
  */
  const mobileMenuOverlay = document.querySelector(".mobile-menu");

  if (mobileMenuOverlay?.closest("#smooth-content")) {
    document.body.appendChild(mobileMenuOverlay);
  }


  /* ========================================
     GSAP SCROLLSMOOTHER
     Native scrollbar + GSAP catch-up smoothing.
     Touch scrolling stays native.
  ======================================== */

  /* ========================================
     MOBILE MENU
  ======================================== */

  const menuToggle = document.querySelector(".menu-toggle");
  const menuClose = document.querySelector(".menu-close");
  const mobileMenu = document.querySelector(".mobile-menu");
  const mobileMenuLinks = document.querySelectorAll(
    ".mobile-menu a[href^='#']"
  );

  const setMenuState = (open) => {
    if (!menuToggle || !mobileMenu) return;
    menuToggle.setAttribute("aria-expanded", String(open));
    mobileMenu.setAttribute("aria-hidden", String(!open));
    mobileMenu.classList.toggle("is-open", open);
    document.body.classList.toggle("menu-open", open);

    if (smoother) {
      smoother.paused(open);
    }
  };

  menuToggle?.addEventListener("click", () => {
    setMenuState(menuToggle.getAttribute("aria-expanded") !== "true");
  });

  menuClose?.addEventListener("click", () => {
    setMenuState(false);
    menuToggle?.focus();
  });

  mobileMenuLinks.forEach((link) => {
    link.addEventListener("click", () => setMenuState(false));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setMenuState(false);
  });

  const desktopMedia = window.matchMedia("(min-width: 1025px)");
  const closeMenuOnDesktop = (event) => {
    if (event.matches) setMenuState(false);
  };

  if (desktopMedia.addEventListener) {
    desktopMedia.addEventListener("change", closeMenuOnDesktop);
  } else {
    desktopMedia.addListener(closeMenuOnDesktop);
  }

  /* ========================================
     FAQ
  ======================================== */

  const faqItems = document.querySelectorAll(".faq-item");

  const closeItem = (item) => {
    const trigger = item.querySelector(".faq-trigger");
    const answer = item.querySelector(".faq-answer");

    if (
      !trigger ||
      !answer ||
      trigger.getAttribute("aria-expanded") !== "true"
    ) return;

    trigger.setAttribute("aria-expanded", "false");

    if (reduceMotion) {
      answer.style.height = "0px";
      answer.hidden = true;
      return;
    }

    answer.style.height = `${answer.scrollHeight}px`;

    requestAnimationFrame(() => {
      answer.style.transition = "height 280ms ease";
      answer.style.height = "0px";
    });

    const done = (event) => {
      if (event.propertyName !== "height") return;
      answer.hidden = true;
      answer.style.removeProperty("height");
      answer.style.removeProperty("transition");
      answer.removeEventListener("transitionend", done);
    };

    answer.addEventListener("transitionend", done);
  };

  const openItem = (item) => {
    const trigger = item.querySelector(".faq-trigger");
    const answer = item.querySelector(".faq-answer");

    if (!trigger || !answer) return;

    faqItems.forEach((other) => {
      if (other !== item) closeItem(other);
    });

    trigger.setAttribute("aria-expanded", "true");
    answer.hidden = false;

    if (reduceMotion) {
      answer.style.height = "auto";
      return;
    }

    answer.style.height = "0px";
    answer.style.transition = "height 280ms ease";

    requestAnimationFrame(() => {
      answer.style.height = `${answer.scrollHeight}px`;
    });

    const done = (event) => {
      if (event.propertyName !== "height") return;
      answer.style.height = "auto";
      answer.style.removeProperty("transition");
      answer.removeEventListener("transitionend", done);
    };

    answer.addEventListener("transitionend", done);
  };

  faqItems.forEach((item) => {
    const trigger = item.querySelector(".faq-trigger");
    trigger?.addEventListener("click", () => {
      const open = trigger.getAttribute("aria-expanded") === "true";
      open ? closeItem(item) : openItem(item);
    });
  });

  /* ========================================
     TEXT ONLY — SLIDE UP
  ======================================== */

  const textSelectors = [
    ".hero-title",
    ".hero-description",
    ".trusted-title",
    ".benefits-heading h2",
    ".benefits-intro",
    ".benefit-copy h3",
    ".benefit-copy p",
    ".section-heading h2",
    ".section-heading > p:last-child",
    ".feature-card-copy h3",
    ".feature-card-copy p",
    ".integration-copy h2",
    ".integration-copy p:not(.section-label)",
    ".how-card-copy h3",
    ".how-card-copy > p",
    ".use-cases-heading h2",
    ".use-cases-description",
    ".use-case-card h3",
    ".use-case-card p",
    ".testimonial-section blockquote",
    ".testimonial-name",
    ".testimonial-role",
    ".faq-copy h2",
    ".faq-description",
    ".faq-question",
    ".faq-answer p",
    ".cta-card h2",
    ".cta-description",
    ".footer-description",
    ".footer-column-title",
    ".footer-links a",
    ".footer-copyright",
  ];

  const splitTextIntoWords = (element) => {
    if (!element || element.dataset.motionSplit === "true") return;

    const walker = document.createTreeWalker(
      element,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          return node.nodeValue.trim()
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT;
        },
      }
    );

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    let index = 0;

    nodes.forEach((node) => {
      const fragment = document.createDocumentFragment();

      node.nodeValue.split(/(\s+)/).forEach((token) => {
        if (!token) return;

        if (/^\s+$/.test(token)) {
          fragment.appendChild(document.createTextNode(token));
          return;
        }

        const clip = document.createElement("span");
        clip.className = "word-clip";

        const word = document.createElement("span");
        word.className = "word";
        word.style.setProperty("--word-index", index);
        word.textContent = token;

        clip.appendChild(word);
        fragment.appendChild(clip);
        index += 1;
      });

      node.parentNode.replaceChild(fragment, node);
    });

    element.classList.add("motion-text");
    element.dataset.motionSplit = "true";
  };

  if (!reduceMotion) {
    document.querySelectorAll(textSelectors.join(",")).forEach((element) => {
      if (!element.classList.contains("magic-text")) {
        splitTextIntoWords(element);
      }
    });
  }

  /* ========================================
     ABOUT — SCROLL COLOR REVEAL
  ======================================== */

  const magicText = document.querySelector(".magic-text");

  const prepareMagicText = (element) => {
    if (!element || element.dataset.magicSplit === "true") return;

    const walker = document.createTreeWalker(
      element,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          return node.nodeValue.trim()
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT;
        },
      }
    );

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    nodes.forEach((node) => {
      const fragment = document.createDocumentFragment();

      node.nodeValue.split(/(\s+)/).forEach((token) => {
        if (!token) return;

        if (/^\s+$/.test(token)) {
          fragment.appendChild(document.createTextNode(token));
          return;
        }

        const word = document.createElement("span");
        word.className = "magic-word";
        word.textContent = token;
        fragment.appendChild(word);
      });

      node.parentNode.replaceChild(fragment, node);
    });

    element.dataset.magicSplit = "true";
  };

  prepareMagicText(magicText);

  const updateMagicText = () => {
    if (!magicText) return;

    const section = magicText.closest(".about-section");
    if (!section) return;

    const words = Array.from(magicText.querySelectorAll(".magic-word"));

    if (reduceMotion) {
      words.forEach((word) => word.classList.add("is-lit"));
      return;
    }

    const rect = section.getBoundingClientRect();
    const vh = window.innerHeight;

    const start = vh * 0.80;
    const end = vh * 0.28;

    const progress = Math.min(
      1,
      Math.max(0, (start - rect.top) / (start - end))
    );

    const amount = progress * words.length;

    words.forEach((word, index) => {
      word.classList.toggle("is-lit", index < amount);
    });
  };

  /* ========================================
     ALL NON-TEXT OBJECTS — FADE UP
  ======================================== */

  const uiSelectors = [
    ".hero-actions .button",
    ".section-label",
    ".brand-mark",
    ".menu-toggle",
    ".logo-marquee",
    ".benefit-card",
    ".feature-card",
    ".feature-visual",
    ".integration-layout",
    ".integration-image-wrap",
    ".how-icon",
    ".how-card-placeholder",
    ".use-case-icon",
    ".testimonial-logo",
    ".testimonial-image",
    ".cta-card",
    ".footer-logo",
    ".footer-watermark",
  ];

  const uiObjects = Array.from(
    document.querySelectorAll(uiSelectors.join(","))
  );

  uiObjects.forEach((element) => {
    element.classList.add("motion-ui");
  });

  /* Benefit images must remain static inside card */
  document.querySelectorAll(".benefit-card .card-art").forEach((art) => {
    art.classList.remove("motion-ui", "is-visible");
  });

  /* Pricing stays static on hover */
  document.querySelectorAll(".pricing-card").forEach((card) => {
    card.classList.remove("interactive-card", "tilt-card");
  });

  /* How cards keep their zoom entrance */
  document.querySelectorAll(".zoom-card").forEach((card) => {
    card.classList.remove("motion-ui", "motion-object");
  });

  /* ========================================
     LEFT→RIGHT, THEN TOP→BOTTOM DELAYS
  ======================================== */

  const assignDelays = () => {
    document.querySelectorAll("main, section, footer").forEach((section) => {
      const items = Array.from(
        section.querySelectorAll(".motion-text, .motion-ui, .zoom-card")
      );

      const unique = [...new Set(items)];

      unique.sort((a, b) => {
        const A = a.getBoundingClientRect();
        const B = b.getBoundingClientRect();

        if (Math.abs(A.top - B.top) > 28) {
          return A.top - B.top;
        }

        return A.left - B.left;
      });

      unique.forEach((element, index) => {
        element.style.setProperty(
          "--motion-delay",
          `${Math.min(index * 65, 390)}ms`
        );
      });
    });
  };

  assignDelays();

  /* ========================================
     ENTRANCE OBSERVER
  ======================================== */

  if (reduceMotion) {
    document.querySelectorAll(
      ".motion-text, .motion-ui, .zoom-card, .magic-text, .integration-button, .use-case-entrance, .pricing-entrance, .faq-entrance, .how-card-copy ul"
    ).forEach((element) => element.classList.add("is-visible"));
  } else {
    const observer = new IntersectionObserver(
      (entries, instance) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;

          entry.target.classList.add("is-visible");
          instance.unobserve(entry.target);
        });
      },
      {
        threshold: 0.14,
        rootMargin: "0px 0px -8% 0px",
      }
    );

    document.querySelectorAll(
      ".motion-text, .motion-ui, .zoom-card, .magic-text, .integration-button, .use-case-entrance, .pricing-entrance, .faq-entrance, .how-card-copy ul"
    ).forEach((element) => {
      /*
        Benefit card position is scroll-driven, not generic fade-up.
        Its text still uses the normal slide-up animation.
      */
      if (element.classList.contains("benefit-card")) {
        element.classList.add("is-visible");
        return;
      }

      observer.observe(element);
    });
  }

  /* ========================================
     BENEFIT — FRAME-BY-FRAME STYLE
     supplied frames:
     fan/overlap → straight overlap → final spread
  ======================================== */

  const benefitGrid = document.querySelector(".benefit-grid");
  const benefitCards = benefitGrid
    ? Array.from(benefitGrid.querySelectorAll(".benefit-card"))
    : [];

  let ticking = false;

  const updateBenefit = () => {
    if (!benefitGrid || benefitCards.length !== 3) return;

    if (window.innerWidth <= 767) {
      benefitCards.forEach((card) => {
        card.style.setProperty("--benefit-shift-x", "0px");
        card.style.setProperty("--benefit-scale", "1");
        card.style.setProperty("--benefit-rotate", "0deg");
      });
      return;
    }

    const rect = benefitGrid.getBoundingClientRect();
    const vh = window.innerHeight;

    const start = vh * 0.92;
    const end = vh * 0.32;

    const progress = Math.min(
      1,
      Math.max(0, (start - rect.top) / (start - end))
    );

    const centers = benefitCards.map((card) => {
      const r = card.getBoundingClientRect();
      return r.left + r.width / 2;
    });

    const centerX = centers[1];

    /* First 38%: cards straighten while staying overlapped */
    const straighten = Math.min(1, progress / 0.38);

    /* Remaining scroll: cards spread to their real positions */
    const spread = Math.max(0, (progress - 0.38) / 0.62);

    const leftShift = (centerX - centers[0]) * 0.68;
    const rightShift = (centerX - centers[2]) * 0.68;
    const remaining = 1 - spread;

    benefitCards[0].style.setProperty(
      "--benefit-shift-x",
      `${leftShift * remaining}px`
    );

    benefitCards[1].style.setProperty(
      "--benefit-shift-x",
      "0px"
    );

    benefitCards[2].style.setProperty(
      "--benefit-shift-x",
      `${rightShift * remaining}px`
    );

    const rotation = 5 * (1 - straighten);

    benefitCards[0].style.setProperty(
      "--benefit-rotate",
      `${-rotation}deg`
    );

    benefitCards[1].style.setProperty(
      "--benefit-rotate",
      "0deg"
    );

    benefitCards[2].style.setProperty(
      "--benefit-rotate",
      `${rotation}deg`
    );

    const scale = 0.96 + 0.04 * spread;

    benefitCards[0].style.setProperty(
      "--benefit-scale",
      String(scale)
    );

    benefitCards[1].style.setProperty(
      "--benefit-scale",
      "1"
    );

    benefitCards[2].style.setProperty(
      "--benefit-scale",
      String(scale)
    );
  };

  const updateScrollMotion = () => {
    ticking = false;
    updateMagicText();
    updateBenefit();
  };

  const requestScrollMotion = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(updateScrollMotion);
  };

  /* ========================================
     CREATE GSAP SCROLLSMOOTHER
  ======================================== */

  if (
    !reduceMotion &&
    window.gsap &&
    window.ScrollTrigger &&
    window.ScrollSmoother
  ) {
    gsap.registerPlugin(ScrollTrigger, ScrollSmoother);

    smoother = ScrollSmoother.create({
      wrapper: "#smooth-wrapper",
      content: "#smooth-content",

      /*
        0.9 = subtle premium catch-up.
        Raise this to ~1.1–1.3 for a softer/heavier feel.
        Lower it to ~0.6–0.75 for a more direct feel.
      */
      smooth: 0.9,

      /*
        Keep phones/tablets connected directly to finger movement.
      */
      smoothTouch: 0,

      /*
        No parallax/lag effects are enabled automatically.
      */
      effects: false,
      normalizeScroll: false,

      /*
        Keep the existing scroll-driven About + Benefits effects
        synchronized while ScrollSmoother is still catching up.
      */
      onUpdate: requestScrollMotion,
    });
  }

  updateScrollMotion();

  window.addEventListener("scroll", requestScrollMotion, {
    passive: true,
  });

  window.addEventListener("resize", () => {
    assignDelays();
    requestScrollMotion();
  });

  window.addEventListener(
    "load",
    () => {
      smoother?.refresh();
      requestScrollMotion();
    },
    { once: true }
  );

  /* ========================================
     USE CASE TILT — NO GLARE / NO SHADOW
  ======================================== */

  document.querySelectorAll(".tilt-card").forEach((card) => {
    card.addEventListener("pointermove", (event) => {
      if (reduceMotion || window.matchMedia("(hover: none)").matches) {
        return;
      }

      const rect = card.getBoundingClientRect();

      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;

      const rotateY = (x - 0.5) * 14;
      const rotateX = (0.5 - y) * 14;

      card.style.setProperty("--tilt-x", `${rotateX.toFixed(2)}deg`);
      card.style.setProperty("--tilt-y", `${rotateY.toFixed(2)}deg`);
    });

    card.addEventListener("pointerleave", () => {
      card.style.setProperty("--tilt-x", "0deg");
      card.style.setProperty("--tilt-y", "0deg");
    });
  });
});