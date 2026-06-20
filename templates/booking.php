<?php
require_once APP_PATH . DIRECTORY_SEPARATOR . 'database.php';

$bookingMessage = '';

if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['book'])) {
    // Collect and sanitize form data
    $checkIn = htmlspecialchars($_POST['check-in']);
    $checkOut = htmlspecialchars($_POST['check-out']);
    $roomType = htmlspecialchars($_POST['room-type']);
    $guests = htmlspecialchars($_POST['guests']);
    $name = htmlspecialchars($_POST['name']);
    $email = htmlspecialchars($_POST['email']);
    $phone = htmlspecialchars($_POST['phone']);

    // Server-side validation
    if (strtotime($checkOut) <= strtotime($checkIn)) {
        $bookingMessage = 'Error: Check-out date must be after check-in date.';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $bookingMessage = 'Error: Invalid email format.';
    } elseif (!preg_match("/^[\+]?([0-9]{1,3})?[-. ]?([0-9]{1,4})?[-. ]?([0-9]{1,4})?[-. ]?([0-9]{1,9})$/", $phone)) {
        $bookingMessage = 'Error: Invalid phone number format. Please enter a valid phone number.';
    } else {
        // Prepare and bind
        $stmt = $conn->prepare("INSERT INTO bookings (check_in, check_out, room_type, guests, name, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?)");
        $stmt->bind_param("sssiiss", $checkIn, $checkOut, $roomType, $guests, $name, $email, $phone);

        // Execute the statement
        if ($stmt->execute()) {
            $bookingMessage = "Thank you for your booking, $name! We will contact you shortly.";
        } else {
            $bookingMessage = 'Error: ' . $stmt->error;
        }

        // Close the statement and connection
        $stmt->close();
        $conn->close();
    }
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hotel Booking - Book Your Stay</title>
    <link rel="stylesheet" href="<?= asset('css/style.css'); ?>">
</head>
<body>
    <header>
        <h1>Book Your Stay</h1>
        <nav>
            <ul>
                <li><a href="<?= url_for(); ?>">Home</a></li>
                <li><a href="<?= url_for('about'); ?>">About</a></li>
                <li><a href="<?= url_for('booking'); ?>">Booking</a></li>
                <li><a href="<?= url_for('contact'); ?>">Contact Us</a></li>
            </ul>
        </nav>
    </header>
    
    <main>
        <!-- Booking Form Section -->
        <section class="booking-form">
    <h2>Reserve Your Room</h2>
    <?php if ($bookingMessage !== ''): ?>
        <p><?= htmlspecialchars($bookingMessage); ?></p>
    <?php endif; ?>
    <form action="<?= url_for('booking'); ?>" method="POST" onsubmit="return validateBookingForm()">
        <div class="form-group">
            <label for="check-in">Check-in Date:</label>
            <input type="date" id="check-in" name="check-in" required>
        </div>
        <div class="form-group">
            <label for="check-out">Check-out Date:</label>
            <input type="date" id="check-out" name="check-out" required>
        </div>
        <div class="form-group">
            <label for="room-type">Room Type:</label>
            <select id="room-type" name="room-type" required>
                <option value="deluxe">Deluxe Room</option>
                <option value="family">Family Suite</option>
                <option value="standard">Standard Room</option>
            </select>
        </div>
        <div class="form-group">
            <label for="guests">Number of Guests:</label>
            <input type="number" id="guests" name="guests" min="1" max="10" required>
        </div>
        <div class="form-group">
            <label for="name">Full Name:</label>
            <input type="text" id="name" name="name" required>
        </div>
        <div class="form-group">
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" required>
        </div>
        <div class="form-group">
            <label for="phone">Phone Number:</label>
            <input type="tel" id="phone" name="phone" required pattern="[\+]?([0-9]{1,3})?[-. ]?([0-9]{1,4})?[-. ]?([0-9]{1,4})?[-. ]?([0-9]{1,9})" title="Please enter a valid phone number.">
        </div>
        <button type="submit" name="book" class="cta-button">Book Now</button>
    </form>
</section>
          
    </main>

    <footer>
        <p>&copy; 2026 Hotel Booking. All rights reserved.</p>
    </footer>

    <script>
        function validateBookingForm() {
            // Additional client-side validation can be added here if needed
            return true; // Allow form submission
        }
    </script>
</body>
</html>
