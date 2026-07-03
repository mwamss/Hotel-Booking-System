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

document.addEventListener("DOMContentLoaded", () => {
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
