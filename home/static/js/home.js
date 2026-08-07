/* ==========================================================================
   Dr Apple — Homepage Interactions
   Requires GSAP + ScrollTrigger (loaded in home.html)
   ========================================================================== */

document.addEventListener("DOMContentLoaded", function () {
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  /* ------------------------------------------------------------------ */
  /* Sticky navbar blur on scroll                                       */
  /* ------------------------------------------------------------------ */
  const navbar = document.querySelector(".dr-navbar");
  if (navbar) {
    const toggleNavbar = () => {
      navbar.classList.toggle("is-scrolled", window.scrollY > 40);
    };
    toggleNavbar();
    window.addEventListener("scroll", toggleNavbar, { passive: true });
  }

  const navToggle = document.querySelector(".nav-toggle");
  const navLinks = document.querySelector(".nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      navLinks.classList.toggle("is-open");
    });
  }

  /* ------------------------------------------------------------------ */
  /* Button ripple effect                                                */
  /* ------------------------------------------------------------------ */
  document.querySelectorAll(".btn-premium").forEach((btn) => {
    btn.addEventListener("click", function (e) {
      const rect = btn.getBoundingClientRect();
      const ripple = document.createElement("span");
      const size = Math.max(rect.width, rect.height);
      ripple.className = "ripple";
      ripple.style.width = ripple.style.height = size + "px";
      ripple.style.left = e.clientX - rect.left - size / 2 + "px";
      ripple.style.top = e.clientY - rect.top - size / 2 + "px";
      btn.appendChild(ripple);
      setTimeout(() => ripple.remove(), 650);
    });
  });

  /* ------------------------------------------------------------------ */
  /* Floating hero particles (generated, lightweight)                    */
  /* ------------------------------------------------------------------ */
  const particleField = document.querySelector(".hero-particles");
  if (particleField && !prefersReducedMotion) {
    const count = 18;
    for (let i = 0; i < count; i++) {
      const p = document.createElement("span");
      p.className = "particle";
      p.style.left = Math.random() * 100 + "%";
      p.style.bottom = Math.random() * 40 + "%";
      p.style.animationDuration = 6 + Math.random() * 6 + "s";
      p.style.animationDelay = Math.random() * 6 + "s";
      p.style.opacity = 0.3 + Math.random() * 0.4;
      particleField.appendChild(p);
    }
  }

  /* ------------------------------------------------------------------ */
  /* GSAP-driven animation, with a plain-CSS fallback if GSAP failed     */
  /* to load (e.g. offline demo environments)                            */
  /* ------------------------------------------------------------------ */
  const hasGSAP = typeof window.gsap !== "undefined";

  if (hasGSAP && !prefersReducedMotion) {
    gsap.registerPlugin(ScrollTrigger);

    // Hero entrance
    gsap.timeline({ defaults: { ease: "power3.out" } })
      .from(".hero-copy .eyebrow", { opacity: 0, y: 16, duration: 0.6 })
      .from(".hero-copy h1", { opacity: 0, y: 24, duration: 0.8 }, "-=0.35")
      .from(".hero-copy p", { opacity: 0, y: 18, duration: 0.7 }, "-=0.5")
      .from(".hero-actions .btn-premium", { opacity: 0, y: 14, stagger: 0.12, duration: 0.6 }, "-=0.4")
      .from(".hero-device", { opacity: 0, scale: 0.9, y: 40, duration: 1 }, "-=0.7");

    // Hero device: slight rotation + drift on scroll
    gsap.to(".hero-device", {
      rotateZ: 4,
      rotateX: -4,
      y: -30,
      ease: "none",
      scrollTrigger: {
        trigger: ".hero",
        start: "top top",
        end: "bottom top",
        scrub: 1,
      },
    });

    // Generic scroll-reveal for any .reveal element
    document.querySelectorAll(".reveal").forEach((el) => {
      gsap.to(el, {
        opacity: 1,
        y: 0,
        duration: 0.9,
        ease: "power3.out",
        scrollTrigger: {
          trigger: el,
          start: "top 85%",
        },
      });
    });

    // Staggered card grids reveal together, in order
    document.querySelectorAll("[data-stagger-group]").forEach((group) => {
      const items = group.querySelectorAll(".reveal");
      gsap.to(items, {
        opacity: 1,
        y: 0,
        duration: 0.8,
        ease: "power3.out",
        stagger: 0.12,
        scrollTrigger: {
          trigger: group,
          start: "top 85%",
        },
      });
    });
  } else {
    // Fallback: IntersectionObserver-based reveal, no scrub/parallax
    const revealEls = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window && revealEls.length) {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.style.transition =
                "opacity 0.7s ease, transform 0.7s ease";
              entry.target.style.opacity = "1";
              entry.target.style.transform = "translateY(0)";
              io.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15 }
      );
      revealEls.forEach((el) => io.observe(el));
    } else {
      revealEls.forEach((el) => {
        el.style.opacity = "1";
        el.style.transform = "none";
      });
    }
  }

  /* ------------------------------------------------------------------ */
  /* Best sellers horizontal slider controls                             */
  /* ------------------------------------------------------------------ */
  const track = document.querySelector(".slider-track");
  const prevBtn = document.querySelector(".slider-btn.prev");
  const nextBtn = document.querySelector(".slider-btn.next");
  if (track && prevBtn && nextBtn) {
    const scrollAmount = () => track.clientWidth * 0.8;
    prevBtn.addEventListener("click", () =>
      track.scrollBy({ left: -scrollAmount(), behavior: "smooth" })
    );
    nextBtn.addEventListener("click", () =>
      track.scrollBy({ left: scrollAmount(), behavior: "smooth" })
    );
  }

  /* ------------------------------------------------------------------ */
  /* Smooth-scroll for on-page anchor links (e.g. nav -> #reviews)       */
  /* ------------------------------------------------------------------ */
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      const targetId = this.getAttribute("href");
      if (targetId.length > 1) {
        const target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    });
  });

  /* ------------------------------------------------------------------ */
  /* Newsletter form: basic client-side handling                         */
  /* Replace with real POST to your Django endpoint + CSRF token         */
  /* ------------------------------------------------------------------ */
  const newsletterForm = document.querySelector(".newsletter-form");
  if (newsletterForm) {
    newsletterForm.addEventListener("submit", function (e) {
      e.preventDefault();
      const emailInput = newsletterForm.querySelector('input[type="email"]');
      const btn = newsletterForm.querySelector(".btn-premium");
      if (emailInput && emailInput.value) {
        const originalText = btn.textContent;
        btn.textContent = "Subscribed ✓";
        btn.style.pointerEvents = "none";
        setTimeout(() => {
          btn.textContent = originalText;
          btn.style.pointerEvents = "auto";
          emailInput.value = "";
        }, 2400);
      }
    });
  }
});