<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hotel Booking - Home</title>
    <link rel="stylesheet" href="<?= asset('css/style.css'); ?>">
</head>
<body>
    <header>
        <h1>Welcome to GSS Hotel</h1>
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
        <!-- Hero Section -->
        <section class="hero">
            <h2>Experience Luxury and Comfort</h2>
            <p>Your perfect getaway awaits. Book your stay today!</p>
            <a href="<?= url_for('booking'); ?>" class="cta-button">Book Now</a>
        </section>

        <!-- Featured Rooms Section -->
        <section class="featured-rooms">
            <h2>Featured Rooms</h2>
            <div class="room">
                <img src="<?= asset('images/room1.jpg'); ?>" alt="Deluxe Room">
                <h3>Deluxe Room</h3>
                <p>Enjoy a luxurious stay with stunning views and modern amenities.</p>
                <a href="<?= url_for('booking'); ?>" class="cta-button">Check Availability</a>
            </div>
            <div class="room">
                <img src="<?= asset('images/room2.jpg'); ?>" alt="Family Suite">
                <h3>Family Suite</h3>
                <p>Perfect for families, spacious and comfortable with all the essentials.</p>
                <a href="<?= url_for('booking'); ?>" class="cta-button">Check Availability</a>
            </div>
            <div class="room">
                <img src="<?= asset('images/room3.jpg'); ?>" alt="Standard Room">
                <h3>Standard Room</h3>
                <p>A cozy room with everything you need for a pleasant stay.</p>
                <a href="<?= url_for('booking'); ?>" class="cta-button">Check Availability</a>
            </div>
        </section>

        <!-- Amenities Section -->
        <section class="amenities">
            <h2>Amenities</h2>
            <ul>
                <li>Free Wi-Fi</li>
                <li>Swimming Pool</li>
                <li>24/7 Room Service</li>
                <li>Fitness Center</li>
                <li>Complimentary Breakfast</li>
            </ul>
        </section>

        <!-- Testimonials Section -->
        <section class="testimonials">
            <h2>What Our Guests Say</h2>
            <blockquote>
                <p>"The best hotel experience I've ever had! Highly recommend!"</p>
                <cite>- John Doe</cite>
            </blockquote>
            <blockquote>
                <p>"Amazing service and beautiful rooms. Will definitely come back!"</p>
                <cite>- Jane Smith</cite>
            </blockquote>
        </section>
    </main>

    <footer>
        <p>&copy; 2026 Hotel Booking. All rights reserved.</p>
    </footer>
</body>
</html>
