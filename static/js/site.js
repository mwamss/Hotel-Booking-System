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

function setFormBusy(form, isBusy, label) {
    const submitButton = form.querySelector("[type='submit']");
    form.setAttribute("aria-busy", String(isBusy));

    [...form.elements].forEach((element) => {
        element.disabled = isBusy;
    });

    if (!submitButton) {
        return;
    }

    if (!submitButton.dataset.defaultLabel) {
        submitButton.dataset.defaultLabel = submitButton.textContent.trim();
    }

    submitButton.textContent = isBusy ? label : submitButton.dataset.defaultLabel;
}

async function submitForm(form, endpoint, messageElement, successText, options = {}) {
    const payload = readForm(form);

    showMessage(messageElement, "Sending...", "success");
    setFormBusy(form, true, options.busyText || "Sending...");

    try {
        const response = await fetch(apiEndpoint(endpoint), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            const firstError = data.errors ? Object.values(data.errors)[0] : "Please check the form and try again.";
            showMessage(messageElement, firstError, "error");
            return;
        }

        if (typeof options.onSuccess === "function") {
            options.onSuccess({ data, form, messageElement, payload, successText });
        } else {
            form.reset();
            showMessage(messageElement, successText, "success");
        }
    } catch (error) {
        if (isBookingEndpoint(endpoint)) {
            try {
                const data = storeOfflineBooking(payload);

                if (typeof options.onSuccess === "function") {
                    options.onSuccess({
                        data,
                        form,
                        messageElement,
                        payload,
                        successText: "Booking saved locally. The hotel can sync it when the backend is available.",
                    });
                } else {
                    form.reset();
                    showMessage(messageElement, "Booking saved locally.", "success");
                }
                return;
            } catch (storageError) {
                showMessage(messageElement, "Unable to save this booking locally. Please try again.", "error");
                return;
            }
        }

        if (isContactEndpoint(endpoint)) {
            try {
                storeOfflineContact(payload);
                form.reset();
                showMessage(messageElement, "Message saved locally. The hotel can sync it when the backend is available.", "success");
                return;
            } catch (storageError) {
                showMessage(messageElement, "Unable to save this message locally. Please try again.", "error");
                return;
            }
        }

        showMessage(messageElement, networkErrorMessage(), "error");
    } finally {
        setFormBusy(form, false);
    }
}

function isBookingEndpoint(endpoint) {
    return /\/api\/bookings$/i.test(endpoint);
}

function isContactEndpoint(endpoint) {
    return /\/api\/contact$/i.test(endpoint);
}

function storeOfflineBooking(payload) {
    const storageKey = "gss_hotel_offline_bookings";
    const rawBookings = window.localStorage.getItem(storageKey);
    const parsedBookings = rawBookings ? JSON.parse(rawBookings) : [];
    const bookings = Array.isArray(parsedBookings) ? parsedBookings : [];
    const booking = {
        id: `LOCAL-${String(bookings.length + 1).padStart(4, "0")}`,
        storage: "browser-json",
        status: "pending",
        created_at: new Date().toISOString(),
        ...payload,
    };

    bookings.push(booking);
    window.localStorage.setItem(storageKey, JSON.stringify(bookings, null, 2));
    return {
        ok: true,
        id: booking.id,
        storage: booking.storage,
        message: "Booking saved locally.",
    };
}

async function confirmStoredBooking(booking) {
    if (booking.storage === "browser-json") {
        return storeOfflineBookingConfirmation(booking);
    }

    const response = await fetch(apiEndpoint("/api/bookings/confirm"), {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            booking_id: booking.id,
            email: booking.email,
            storage: booking.storage,
        }),
    });
    const data = await response.json();

    if (!response.ok || !data.ok) {
        throw new Error(data.errors ? Object.values(data.errors)[0] : "Unable to confirm booking.");
    }

    return data;
}

function storeOfflineBookingConfirmation(booking) {
    const storageKey = "gss_hotel_offline_booking_confirmations";
    const rawConfirmations = window.localStorage.getItem(storageKey);
    const parsedConfirmations = rawConfirmations ? JSON.parse(rawConfirmations) : [];
    const confirmations = Array.isArray(parsedConfirmations) ? parsedConfirmations : [];
    const confirmedAt = new Date().toISOString();
    const confirmation = {
        id: `LOCAL-${String(confirmations.length + 1).padStart(4, "0")}`,
        booking_id: booking.id,
        booking_reference: booking.reference || booking.id,
        email: booking.email,
        storage: booking.storage || "browser-json",
        status: "confirmed",
        confirmed_at: confirmedAt,
    };

    confirmations.push(confirmation);
    window.localStorage.setItem(storageKey, JSON.stringify(confirmations, null, 2));
    markOfflineBookingConfirmed(booking.id, booking.email, confirmedAt);
    return {
        ok: true,
        id: confirmation.id,
        status: "confirmed",
        storage: "browser-json",
        message: "Booking confirmed locally.",
    };
}

function markOfflineBookingConfirmed(bookingId, email, confirmedAt) {
    const storageKey = "gss_hotel_offline_bookings";
    const rawBookings = window.localStorage.getItem(storageKey);
    const parsedBookings = rawBookings ? JSON.parse(rawBookings) : [];
    const bookings = Array.isArray(parsedBookings) ? parsedBookings : [];
    let changed = false;

    bookings.forEach((booking) => {
        const sameId = String(booking.id) === String(bookingId);
        const sameEmail = String(booking.email || "").toLowerCase() === String(email || "").toLowerCase();

        if (sameId && sameEmail) {
            booking.status = "confirmed";
            booking.confirmed_at = confirmedAt;
            changed = true;
        }
    });

    if (changed) {
        window.localStorage.setItem(storageKey, JSON.stringify(bookings, null, 2));
    }
}

function storeOfflineContact(payload) {
    const storageKey = "gss_hotel_offline_contacts";
    const rawContacts = window.localStorage.getItem(storageKey);
    const parsedContacts = rawContacts ? JSON.parse(rawContacts) : [];
    const contacts = Array.isArray(parsedContacts) ? parsedContacts : [];
    const contact = {
        id: `LOCAL-${String(contacts.length + 1).padStart(4, "0")}`,
        storage: "browser-json",
        created_at: new Date().toISOString(),
        ...payload,
    };

    contacts.push(contact);
    window.localStorage.setItem(storageKey, JSON.stringify(contacts, null, 2));
    return {
        ok: true,
        id: contact.id,
        storage: contact.storage,
        message: "Message saved locally.",
    };
}

function apiEndpoint(endpoint) {
    if (/^https?:\/\//i.test(endpoint)) {
        return endpoint;
    }

    const currentHost = window.location.hostname;
    const currentPort = window.location.port;
    const isLocalHttpPreview = ["localhost", "127.0.0.1", "::1"].includes(currentHost) && currentPort !== "5000";

    if (window.location.protocol === "file:" || isLocalHttpPreview) {
        return `http://127.0.0.1:5000${endpoint}`;
    }

    return endpoint;
}

function networkErrorMessage() {
    const currentHost = window.location.hostname;
    const currentPort = window.location.port;
    const isLocalHttpPreview = ["localhost", "127.0.0.1", "::1"].includes(currentHost) && currentPort !== "5000";

    if (window.location.protocol === "file:" || isLocalHttpPreview) {
        return "Start the Flask backend, then submit again or open http://127.0.0.1:5000/booking.html.";
    }

    return "Unable to send right now. Make sure the Flask backend is running, then try again.";
}

const roomRates = {
    deluxe: 14500,
    executive: 21500,
    presidential: 38500,
};

function formatDisplayDate(value) {
    const date = new Date(`${value}T00:00:00`);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat("en", {
        month: "short",
        day: "numeric",
        year: "numeric",
    }).format(date);
}

function formatRoomType(value) {
    const roomLabels = {
        deluxe: "Deluxe Room",
        executive: "Executive Suite",
        presidential: "Presidential Suite",
        suite: "Suite",
    };

    return roomLabels[value] || value;
}

function formatCurrency(value) {
    return new Intl.NumberFormat("en-KE", {
        style: "currency",
        currency: "KES",
        maximumFractionDigits: 0,
    }).format(value);
}

function calculateNights(checkInValue, checkOutValue) {
    const checkIn = new Date(`${checkInValue}T00:00:00`);
    const checkOut = new Date(`${checkOutValue}T00:00:00`);

    if (Number.isNaN(checkIn.getTime()) || Number.isNaN(checkOut.getTime()) || checkOut <= checkIn) {
        return 0;
    }

    return Math.round((checkOut - checkIn) / 86400000);
}

function selectedRoomInput(form) {
    return form.querySelector("[name='room-type']:checked") || form.querySelector("[name='room-type']");
}

function selectedRoomRate(form, roomType) {
    const selectedRoom = selectedRoomInput(form);
    const explicitRate = Number(selectedRoom?.dataset.roomRate || 0);

    return explicitRate || roomRates[roomType] || 0;
}

function updateStaySummary(form) {
    const payload = readForm(form);
    const nights = calculateNights(payload.check_in, payload.check_out);
    const roomType = payload.room_type || selectedRoomInput(form)?.value || "deluxe";
    const rate = selectedRoomRate(form, roomType);
    const guests = Number(payload.guests || 0);
    const estimate = nights && rate ? formatCurrency(nights * rate) : "Complete dates";
    const nightLabel = nights ? `${nights} night${nights === 1 ? "" : "s"}` : "Select dates";
    const dateLabel = payload.check_in && payload.check_out && nights
        ? `${formatDisplayDate(payload.check_in)} to ${formatDisplayDate(payload.check_out)}`
        : "Select check-in and check-out";
    const guestLabel = guests
        ? `${guests} guest${guests === 1 ? "" : "s"}`
        : "Add guests";
    const summaryValues = {
        dates: dateLabel,
        nights: nightLabel,
        room: formatRoomType(roomType),
        guests: guestLabel,
        estimate,
    };

    Object.entries(summaryValues).forEach(([key, value]) => {
        document.querySelectorAll(`[data-summary="${key}"]`).forEach((target) => {
            target.textContent = value;
        });
    });
}

function setupBookingDates(form) {
    const checkIn = form.querySelector("#check-in");
    const checkOut = form.querySelector("#check-out");

    if (!checkIn || !checkOut) {
        return;
    }

    const today = new Date();
    const todayIso = [
        today.getFullYear(),
        String(today.getMonth() + 1).padStart(2, "0"),
        String(today.getDate()).padStart(2, "0"),
    ].join("-");
    checkIn.min = todayIso;
    checkOut.min = todayIso;

    const syncDateValidity = () => {
        checkOut.min = checkIn.value || todayIso;
        checkOut.setCustomValidity("");

        if (checkOut.value && checkIn.value && checkOut.value <= checkIn.value) {
            checkOut.setCustomValidity("Check-out must be after check-in.");
        }

        updateStaySummary(form);
    };

    checkIn.addEventListener("change", () => {
        syncDateValidity();

        if (checkOut.value && checkIn.value && checkOut.value <= checkIn.value) {
            checkOut.value = "";
        }
    });

    checkOut.addEventListener("change", syncDateValidity);
    syncDateValidity();
}

function showBookingConfirmation({ data, form, messageElement, payload, successText }) {
    const confirmation = document.querySelector("#booking-confirmation");
    const confirmButton = document.querySelector("#confirm-booking-button");
    const confirmStatus = document.querySelector("#booking-confirm-status");

    if (!confirmation) {
        form.reset();
        showMessage(messageElement, successText, "success");
        return;
    }

    const reference = data.storage === "browser-json" && data.id
        ? data.id
        : data.id
            ? `GSS-${String(data.id).padStart(4, "0")}`
            : "Pending";
    const dates = `${formatDisplayDate(payload.check_in)} to ${formatDisplayDate(payload.check_out)}`;
    const room = `${formatRoomType(payload.room_type)} for ${payload.guests} guest${payload.guests === "1" ? "" : "s"}`;
    const contact = `${payload.name} - ${payload.email}`;

    confirmation.dataset.bookingId = data.id || "";
    confirmation.dataset.bookingReference = reference;
    confirmation.dataset.bookingEmail = payload.email;
    confirmation.dataset.bookingStorage = data.storage || "database";

    document.querySelector("#confirmation-reference").textContent = reference;
    document.querySelector("#confirmation-dates").textContent = dates;
    document.querySelector("#confirmation-room").textContent = room;
    document.querySelector("#confirmation-contact").textContent = contact;

    if (confirmStatus) {
        confirmStatus.textContent = "Ready for guest confirmation.";
        confirmStatus.classList.remove("is-confirmed", "is-error");
    }

    if (confirmButton) {
        confirmButton.disabled = false;
        confirmButton.textContent = "Confirm booking";
    }

    form.reset();
    form.hidden = true;
    messageElement.hidden = true;
    confirmation.hidden = false;
    confirmation.scrollIntoView({ behavior: "smooth", block: "start" });
}

function setupBookingConfirmationReset(form) {
    const confirmation = document.querySelector("#booking-confirmation");
    const newBookingButton = document.querySelector("#new-booking-button");
    const confirmButton = document.querySelector("#confirm-booking-button");
    const confirmStatus = document.querySelector("#booking-confirm-status");
    const message = document.querySelector("#booking-message");

    if (!confirmation || !newBookingButton) {
        return;
    }

    if (confirmButton) {
        confirmButton.addEventListener("click", async () => {
            const booking = {
                id: confirmation.dataset.bookingId,
                reference: confirmation.dataset.bookingReference,
                email: confirmation.dataset.bookingEmail,
                storage: confirmation.dataset.bookingStorage,
            };

            if (!booking.id || !booking.email) {
                if (confirmStatus) {
                    confirmStatus.textContent = "Booking details are missing. Please submit the request again.";
                    confirmStatus.classList.add("is-error");
                }
                return;
            }

            confirmButton.disabled = true;
            confirmButton.textContent = "Confirming...";

            try {
                await confirmStoredBooking(booking);

                if (confirmStatus) {
                    confirmStatus.textContent = "Booking confirmed. Keep the reference for check-in.";
                    confirmStatus.classList.add("is-confirmed");
                    confirmStatus.classList.remove("is-error");
                }

                confirmButton.textContent = "Booking confirmed";
            } catch (error) {
                try {
                    storeOfflineBookingConfirmation(booking);

                    if (confirmStatus) {
                        confirmStatus.textContent = "Booking confirmed locally. The hotel can sync it when the backend is available.";
                        confirmStatus.classList.add("is-confirmed");
                        confirmStatus.classList.remove("is-error");
                    }

                    confirmButton.textContent = "Booking confirmed";
                } catch (storageError) {
                    confirmButton.disabled = false;
                    confirmButton.textContent = "Confirm booking";

                    if (confirmStatus) {
                        confirmStatus.textContent = "Unable to confirm right now. Please try again.";
                        confirmStatus.classList.add("is-error");
                        confirmStatus.classList.remove("is-confirmed");
                    }
                }
            }
        });
    }

    newBookingButton.addEventListener("click", () => {
        confirmation.hidden = true;
        form.hidden = false;
        form.reset();
        setBookingStep(form, 0);
        updateStaySummary(form);
        delete confirmation.dataset.bookingId;
        delete confirmation.dataset.bookingReference;
        delete confirmation.dataset.bookingEmail;
        delete confirmation.dataset.bookingStorage;

        if (confirmStatus) {
            confirmStatus.textContent = "Ready for guest confirmation.";
            confirmStatus.classList.remove("is-confirmed", "is-error");
        }

        if (message) {
            message.hidden = true;
        }

        form.querySelector("input, select, textarea")?.focus();
    });
}

function bookingStepPanels(form) {
    return [...form.querySelectorAll("[data-step-panel]")];
}

function bookingStepIndicators() {
    return [...document.querySelectorAll("[data-step-indicator]")];
}

function activeBookingStepIndex(form) {
    return Number(form.dataset.activeStep || "0");
}

function validateBookingStep(panel) {
    const fields = [...panel.querySelectorAll("input, select, textarea")];

    for (const field of fields) {
        if (!field.checkValidity()) {
            field.reportValidity();
            return false;
        }
    }

    return true;
}

function setBookingStep(form, nextIndex) {
    const panels = bookingStepPanels(form);
    const indicators = bookingStepIndicators();
    const boundedIndex = Math.max(0, Math.min(nextIndex, panels.length - 1));

    panels.forEach((panel, index) => {
        panel.hidden = index !== boundedIndex;
        panel.classList.toggle("is-active", index === boundedIndex);
    });

    indicators.forEach((indicator, index) => {
        indicator.classList.toggle("active", index === boundedIndex);
        indicator.classList.toggle("is-complete", index < boundedIndex);
        indicator.setAttribute("aria-current", index === boundedIndex ? "step" : "false");
    });

    form.dataset.activeStep = String(boundedIndex);

    if (boundedIndex === panels.length - 1) {
        updateBookingReview(form);
    }
}

function updateBookingReview(form) {
    const payload = readForm(form);
    const nights = calculateNights(payload.check_in, payload.check_out);
    const rate = selectedRoomRate(form, payload.room_type);
    const dates = payload.check_in && payload.check_out
        ? `${formatDisplayDate(payload.check_in)} to ${formatDisplayDate(payload.check_out)}`
        : "Select dates";
    const room = payload.room_type && payload.guests
        ? `${formatRoomType(payload.room_type)} for ${payload.guests} guest${payload.guests === "1" ? "" : "s"}`
        : "Choose a room";
    const guest = payload.name ? payload.name : "Add guest name";
    const contact = payload.email && payload.phone
        ? `${payload.email} - ${payload.phone}`
        : "Add contact details";
    const estimate = nights && rate ? formatCurrency(nights * rate) : "Complete dates";

    const reviewValues = {
        dates,
        room,
        guest,
        contact,
        estimate,
    };

    Object.entries(reviewValues).forEach(([key, value]) => {
        const target = document.querySelector(`[data-review="${key}"]`);

        if (target) {
            target.textContent = value;
        }
    });
}

function setupBookingFlow(form) {
    const panels = bookingStepPanels(form);

    if (panels.length === 0) {
        return;
    }

    setBookingStep(form, 0);

    form.addEventListener("click", (event) => {
        const nextButton = event.target.closest("[data-next-step]");
        const prevButton = event.target.closest("[data-prev-step]");

        if (nextButton) {
            const activeIndex = activeBookingStepIndex(form);

            if (validateBookingStep(panels[activeIndex])) {
                setBookingStep(form, activeIndex + 1);
            }
        }

        if (prevButton) {
            setBookingStep(form, activeBookingStepIndex(form) - 1);
        }
    });

    form.addEventListener("input", () => {
        updateStaySummary(form);

        if (activeBookingStepIndex(form) === panels.length - 1) {
            updateBookingReview(form);
        }
    });

    form.addEventListener("change", () => {
        updateStaySummary(form);

        if (activeBookingStepIndex(form) === panels.length - 1) {
            updateBookingReview(form);
        }
    });
}

function shouldSubmitBookingForm(form) {
    const panels = bookingStepPanels(form);
    const activeIndex = activeBookingStepIndex(form);

    if (activeIndex < panels.length - 1) {
        if (validateBookingStep(panels[activeIndex])) {
            setBookingStep(form, activeIndex + 1);
        }

        return false;
    }

    for (const panel of panels) {
        const invalidField = [...panel.querySelectorAll("input, select, textarea")]
            .find((field) => !field.checkValidity());

        if (invalidField) {
            setBookingStep(form, Number(panel.dataset.stepPanel || "0"));
            window.requestAnimationFrame(() => invalidField.reportValidity());
            return false;
        }
    }

    updateBookingReview(form);
    return true;
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
        ".editorial-intro > *",
        ".arrival-card",
        ".signature-suite-section > *",
        ".seasonal-section .section-title",
        ".seasonal-card",
        ".dining-section > *",
        ".wellness-panel",
        ".recognition-section > *",
        ".neighbourhood-section > *",
        ".newsletter-section > *",
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

function setupHomeMicroInteractions() {
    const header = document.querySelector(".home-header");
    const heroImage = document.querySelector("[data-hero-image]");
    const interactiveCards = [...document.querySelectorAll("[data-micro-card]")];
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let ticking = false;

    const updateScrollState = () => {
        ticking = false;

        if (header) {
            header.classList.toggle("is-compact", window.scrollY > 24);
        }

        if (heroImage && !prefersReducedMotion) {
            const offset = Math.min(window.scrollY / 18, 18);
            heroImage.style.setProperty("--hero-shift-y", `${offset}px`);
        }
    };

    const requestScrollUpdate = () => {
        if (ticking) {
            return;
        }

        ticking = true;
        window.requestAnimationFrame(updateScrollState);
    };

    updateScrollState();
    window.addEventListener("scroll", requestScrollUpdate, { passive: true });

    interactiveCards.forEach((card) => {
        card.addEventListener("pointermove", (event) => {
            const rect = card.getBoundingClientRect();
            const x = ((event.clientX - rect.left) / rect.width) * 100;
            const y = ((event.clientY - rect.top) / rect.height) * 100;

            card.style.setProperty("--mx", `${x}%`);
            card.style.setProperty("--my", `${y}%`);
        });

        card.addEventListener("pointerleave", () => {
            card.style.removeProperty("--mx");
            card.style.removeProperty("--my");
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    setupPageMotion();
    setupHomeMicroInteractions();

    const bookingForm = document.querySelector("#booking-form");
    const bookingMessage = document.querySelector("#booking-message");

    if (bookingForm) {
        setupBookingDates(bookingForm);
        setupBookingFlow(bookingForm);
        setupBookingConfirmationReset(bookingForm);
        updateStaySummary(bookingForm);

        bookingForm.addEventListener("submit", (event) => {
            event.preventDefault();

            if (!shouldSubmitBookingForm(bookingForm)) {
                return;
            }

            submitForm(bookingForm, "/api/bookings", bookingMessage, "Booking request received. We will follow up soon.", {
                busyText: "Sending request...",
                onSuccess: showBookingConfirmation,
            });
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
