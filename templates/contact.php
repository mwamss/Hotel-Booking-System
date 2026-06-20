<?php
require_once APP_PATH . DIRECTORY_SEPARATOR . 'database.php';

$contactMessage = '';

if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['submit'])) {
    // Collect and sanitize form data
    $name = htmlspecialchars($_POST['name']);
    $email = htmlspecialchars($_POST['email']);
    $message = htmlspecialchars($_POST['message']);

    // Prepare and bind
    $stmt = $conn->prepare("INSERT INTO contacts (name, email, message) VALUES (?, ?, ?)");
    $stmt->bind_param("sss", $name, $email, $message);

    // Execute the statement
    if ($stmt->execute()) {
        $contactMessage = "Thank you for contacting us, $name! We will get back to you soon.";
    } else {
        $contactMessage = 'Error: ' . $stmt->error;
    }

    // Close the statement and connection
    $stmt->close();
    $conn->close();
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact Us - Hotel Booking</title>
    <link rel="stylesheet" href="<?= asset('css/style.css'); ?>">
</head>
<body>
    <header>
        <h1>Contact Us</h1>
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
        <!-- Contact Form Section -->
        <section class="contact-form">
            <h2>Get in Touch</h2>
            <?php if ($contactMessage !== ''): ?>
                <p><?= htmlspecialchars($contactMessage); ?></p>
            <?php endif; ?>
            <form action="<?= url_for('contact'); ?>" method="POST">
                <div class="form-group">
                    <label for="name">Full Name:</label>
                    <input type="text" id="name" name="name" required>
                </div>
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" required>
                </div>
                <div class="form-group">
                    <label for="message">Message:</label>
                    <textarea id="message" name="message" rows="5" required></textarea>
                </div>
                <button type="submit" name="submit" class="cta-button">Send Message</button>
            </form>
        </section>
    </main>

    <footer>
        <p>&copy; 2026 Hotel Booking. All rights reserved.</p>
    </footer>
</body>
</html>
