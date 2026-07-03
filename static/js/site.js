function readForm(form) {
    const payload = {};

    for (const [key, value] of new FormData(form).entries()) {
        payload[key.replaceAll("-", "_")] = value;
    }

    return payload;
}

function showMessage(element, text, type) {
    if (!element) {
        return;
    }

    element.textContent = text;
    element.hidden = false;
    element.classList.remove("success", "error");
    element.classList.add(type);
}

async function submitForm(form, endpoint, messageElement, successText) {
    showMessage(messageElement, "Sending...", "success");

    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(readForm(form)),
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            const firstError = data.errors ? Object.values(data.errors)[0] : "Please check the form and try again.";
            showMessage(messageElement, firstError, "error");
            return;
        }

        form.reset();
        showMessage(messageElement, successText, "success");
    } catch (error) {
        showMessage(messageElement, "Unable to send right now. Please try again.", "error");
    }
}

function setupPageMotion() {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.body.classList.add("motion-ready");

    const revealSelectors = [
        ".booking-strip",
        ".intro-copy",
        ".intro-grid article",
        ".section-title",
        ".amenities-grid article",
        ".gallery-grid img",
        ".review-copy",
        ".reviews-grid blockquote",
        ".split-copy",
        ".split-section img",
        ".section-heading",
        ".value-grid article",
        ".image-feature-section img",
        ".image-feature-section > div",
        ".booking-aside > *",
        ".booking-form",
        ".contact-form",
        ".contact-card > *",
    ];

    const revealElements = [...document.querySelectorAll(revealSelectors.join(","))]
        .filter((element) => !element.closest(".room-card"));

    revealElements.forEach((element, index) => {
        element.classList.add("motion-reveal");
        element.style.setProperty("--motion-delay", `${Math.min(index % 4, 3) * 70}ms`);

        if (element.matches("img")) {
            element.dataset.motion = "image";
        }
    });

    if (prefersReducedMotion || !("IntersectionObserver" in window)) {
        revealElements.forEach((element) => element.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    return;
                }

                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            });
        },
        {
            threshold: 0.14,
            rootMargin: "0px 0px -8% 0px",
        }
    );

    revealElements.forEach((element) => observer.observe(element));
}

document.addEventListener("DOMContentLoaded", () => {
    setupPageMotion();

    const bookingForm = document.querySelector("#booking-form");
    const bookingMessage = document.querySelector("#booking-message");

    if (bookingForm) {
        bookingForm.addEventListener("submit", (event) => {
            event.preventDefault();
            submitForm(bookingForm, "/api/bookings", bookingMessage, "Booking request received. We will follow up soon.");
        });
    }

    const contactForm = document.querySelector("#contact-form");
    const contactMessage = document.querySelector("#contact-message");

    if (contactForm) {
        contactForm.addEventListener("submit", (event) => {
            event.preventDefault();
            submitForm(contactForm, "/api/contact", contactMessage, "Message received. Our team will get back to you.");
        });
    }
});
