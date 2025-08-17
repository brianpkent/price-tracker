# 🛒 Price Tracker

A minimal local price watcher script in Python.  
Tracks product pages, stores prices in SQLite, and alerts when prices drop below your target.

---

## 🚀 Setup

1. Clone the repo  
   `git clone https://github.com/brianpkent/price-tracker.git && cd price-tracker`

2. Create your config  
   Copy the example file:  
   `cp products.example.yaml products.yaml`  
   Then edit `products.yaml` with your own products.

   Example:
   ```yaml
   products:
     - name: "My Example Product"
       url: "https://www.example.com/product"
       selector: "span.price"
       target_price: 49.99
