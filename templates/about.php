<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hotel Booking - About</title>
    <link rel="stylesheet" href="<?= asset('css/style.css'); ?>">
</head>
<body>
    <header>
        <h1>About GSS Hotel</h1>
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
        <!-- Our Story Section -->
        <section class="our-story">
            <h2>Our Story</h2>
            <p>Founded in 2020, our hotel has been dedicated to providing exceptional service and unforgettable experiences. Nestled in the heart of the city, we offer a perfect blend of luxury and comfort.</p>
            <p>Our mission is to create a home away from home for our guests, ensuring that every stay is memorable. We pride ourselves on our attention to detail and commitment to excellence.</p>
        </section>

        <!-- Our Values Section -->
        <section class="our-values">
            <h2>Our Values</h2>
            <ul>
                <li><strong>Hospitality:</strong> We treat our guests like family.</li>
                <li><strong>Integrity:</strong> We uphold the highest standards of honesty and transparency.</li>
                <li><strong>Excellence:</strong> We strive for perfection in everything we do.</li>
                <li><strong>Community:</strong> We believe in giving back to the community that supports us.</li>
            </ul>
        </section>

        <!-- Meet Our Team Section -->
        <section class="meet-our-team">
            <h2>Meet Our Team</h2>
            <div class="team-member">
                <img src="<?= asset('images/team1.jpg'); ?>" alt="John Doe">
                <h3>John Doe</h3>
                <p>General Manager</p>
                <p>With over 15 years of experience in the hospitality industry, John leads our team with passion and dedication.</p>
            </div>
            <div class="team-member">
                <img src="<?= asset('images/team2.jpg'); ?>" alt="Jane Smith">
                <h3>Jane Smith</h3>
                <p>Head Chef</p>
                <p>Jane creates culinary masterpieces that delight our guests, using only the freshest ingredients.</p>
            </div>
            <div class="team-member">
                <img src="<?= asset('images/team3.jpg'); ?>" alt="Emily Johnson">
                <h3>Emily Johnson</h3>
                <p>Guest Relations Manager</p>
                <p>Emily ensures that every guest feels welcome and valued, providing personalized service at every turn.</p>
            </div>
        </section>

        <!-- Our Facilities Section -->
        <section class="our-facilities">
            <h2>Our Facilities</h2>
            <p>We offer a range of facilities to make your stay comfortable and enjoyable:</p>
            <ul>
                <li>Luxurious Rooms and Suites</li>
                <li>State-of-the-Art Fitness Center</li>
                <li>Relaxing Spa and Wellness Center</li>
                <li>Outdoor Swimming Pool</li>
                <li>On-Site Restaurant and Bar</li>
            </ul>
        </section>
    </main>

    <footer>
        <p>&copy; 2026 Hotel Booking. All rights reserved.</p>
    </footer>
</body>
</html>
