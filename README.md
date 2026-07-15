# SmartCart: AI-Powered E-Commerce Platform
### Final Year Project | Bachelor of Science in Computer Science & Information Technology

SmartCart is a comprehensive, full-stack enterprise e-commerce platform engineered as a final year capstone project. The system seamlessly integrates modern web development paradigms with artificial intelligence to deliver an optimized, scalable, and highly interactive shopping experience. 

Built using a robust architecture with **Python** and the **Django Framework**, the platform incorporates secure transaction handling, real-time inventory management, advanced multi-faceted search, and an intelligent AI-driven customer assistance and product recommendation system powered by the **Gemini API**.

---

## 🚀 Key Features 

### 1. User Authentication & Profile Management
*   **Secure Authentication:** Custom user models supporting secure registration, login, and password recovery via encrypted tokens.
*   **Role-Based Access Control (RBAC):** Distinct interfaces and permissions for Customers, Vendors, and Administrators.
*   **User Profiles:** Comprehensive dashboards for tracking order histories, shipping addresses, payment profiles, and personalized wishlists.

### 2. Product Catalog & Advanced Search
*   **Dynamic Categorization:** Multi-level nesting for product categories and tags.
*   **Multi-Faceted Filtering:** Real-time client-side and server-side filtering by price range, brand, rating, and availability.
*   **Smart Search:** A high-performance search mechanism capable of handling typos, synonyms, and partial matches.

### 3. Shopping Cart & Checkout Workflow
*   **Persistent Shopping Cart:** Session-based and database-persistent shopping carts ensuring zero data loss across user sessions.
*   **Coupon & Discount Engine:** Flexible promotional code verification with automatic subtotal adjustments.
*   **Automated Tax & Shipping Calculation:** Dynamic calculation based on regional geocoding and shipping tier selection.

### 4. AI-Driven Capabilities
*   **Intelligent Support Chatbot:** An embedded customer support agent powered by the **Gemini API** trained to answer order queries, policy questions, and product inquiries.
*   **Smart Product Recommendations:** Content-based filtering engine predicting and rendering "Products You May Like" based on browsing behavior and historical interaction metadata.
*   **Automated Product Tagging:** Computer vision/NLP pipelines that automatically generate descriptive tags and optimized titles during vendor product image uploads.

### 5. Secure Payment Integration & Ordering
*   **Payment Gateway Endpoints:** Complete integration with secure sandboxes (Stripe / PayPal / Local APIs) for processing credit/debit tokens safely.
*   **Order Fulfillment Lifecycle:** End-to-end status tracking from Pending → Processing → Shipped → Delivered → Cancelled.
*   **Invoice Generation:** Automated, beautifully styled PDF invoice generation dispatched directly to user emails upon successful transaction callbacks.

### 6. Administrative Analytics Dashboard
*   **Sales Visualizations:** Interactive graphical summaries showcasing revenue trends, top-performing product categories, and monthly user sign-ups.
*   **Inventory Control:** Low-stock alert triggers notifying administrators when product quantities drop below safe thresholds.

---

## 🛠️ System Architecture & Tech Stack

### Backend
*   **Language:** Python 3.10+
*   **Core Framework:** Django 5.0 (Model-View-Template pattern)
*   **API Architecture:** Django REST Framework (DRF) for decouple-ready endpoints

### Frontend
*   **Structure/Styling:** HTML5, CSS3, Modern UI components, Bootstrap 5 / TailwindCSS
*   **Interactivity:** Vanilla JavaScript (ES6+) / Async AJAX for seamless, page-refresh-free cart interactions

### Database & Storage
*   **Relational Database:** PostgreSQL (Production) / SQLite (Local Development)
*   **Caching & Session Management:** Redis (Optional for caching frequently hit catalog items)
*   **Media Assets:** Local storage / Amazon S3 bucket configuration ready

### External APIs & Third-Party Services
*   **Core AI Integration:** Google Gemini API / Google AI Studio SDK
*   **Payment Services:** Stripe API Core
*   **Email Dispatches:** SMTP Configuration / SendGrid API

---

## 📋 Database Schema Design Overview

The database uses a clean, highly relational schema mapping optimized for ACID compliance:

```text
[User] 1 -------- 1 [UserProfile]
  |
  +-- 1 ---- * [Order] 1 ---- * [OrderItem] * ---- 1 [Product]
  |                                                     |
  +-- 1 ---- 1 [Cart] 1 ------ * [CartItem] * ----------+
                                                        |
                                                 * ---- 1 [Category]
