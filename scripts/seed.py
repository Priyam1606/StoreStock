import json
import random
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.db import get_connection, init_db, transaction
from app.security import hash_password


def main() -> None:
    init_db()
    conn = get_connection()
    try:
        count_row = conn.execute("SELECT COUNT(*) AS total FROM products").fetchone()
        if count_row["total"] > 0:
            sys.stderr.write("Products table is not empty; refusing to seed.\n")
            sys.exit(1)

        kolkata_tz = ZoneInfo("Asia/Kolkata")
        now_k = datetime.now(kolkata_tz)
        today_date = now_k.date()
        now_utc_iso = now_k.astimezone(timezone.utc).isoformat()

        with transaction(conn):
            h_owner = hash_password("owner123")
            h_staff = hash_password("staff123")

            cur = conn.execute("SELECT id FROM users WHERE username = 'owner'").fetchone()
            if not cur:
                c1 = conn.execute(
                    "INSERT INTO users (username, password_hash, role, active, created_at) VALUES ('owner', ?, 'owner', 1, ?)",
                    (h_owner, now_utc_iso),
                )
                owner_id = int(c1.lastrowid)
            else:
                owner_id = int(cur["id"])

            cur = conn.execute("SELECT id FROM users WHERE username = 'staff'").fetchone()
            if not cur:
                c2 = conn.execute(
                    "INSERT INTO users (username, password_hash, role, active, created_at) VALUES ('staff', ?, 'staff', 1, ?)",
                    (h_staff, now_utc_iso),
                )
                staff_id = int(c2.lastrowid)
            else:
                staff_id = int(cur["id"])

            cur = conn.execute("SELECT id FROM users WHERE username = 'staff2'").fetchone()
            if not cur:
                c3 = conn.execute(
                    "INSERT INTO users (username, password_hash, role, active, created_at) VALUES ('staff2', ?, 'staff', 1, ?)",
                    (h_staff, now_utc_iso),
                )
                staff2_id = int(c3.lastrowid)
            else:
                staff2_id = int(cur["id"])

            user_pool = [owner_id, staff_id, staff2_id]

            sup1 = conn.execute(
                "INSERT INTO suppliers (name, phone, active, created_at) VALUES ('Shree Ganesh Wholesale Distributors', '9822211101', 1, ?)",
                (now_utc_iso,),
            )
            sup1_id = int(sup1.lastrowid)

            sup2 = conn.execute(
                "INSERT INTO suppliers (name, phone, active, created_at) VALUES ('Balaji Food & Provision Suppliers', '9822211102', 1, ?)",
                (now_utc_iso,),
            )
            sup2_id = int(sup2.lastrowid)

            sup3 = conn.execute(
                "INSERT INTO suppliers (name, phone, active, created_at) VALUES ('Om Sai Toiletries & Household Wholesale', '9822211103', 1, ?)",
                (now_utc_iso,),
            )
            sup3_id = int(sup3.lastrowid)

            cust_specs = [
                ("Ramesh Kumar", "9811100001", 100000, 1),
                ("Sunita Sharma", "9811100002", 200000, 1),
                ("Amit Patel", "9811100003", 150000, 1),
                ("Vikram Malhotra", "9811100004", 50000, 0),
                ("Priya Nair", "9811100005", 300000, 1),
                ("Rajesh Gupta", "9811100006", 250000, 1),
                ("Ananya Iyer", "9811100007", 500000, 1),
                ("Manoj Singh", "9811100008", 150000, 1),
            ]
            cust_map: dict[str, int] = {}
            for c_name, c_phone, c_lim, c_act in cust_specs:
                c_cur = conn.execute(
                    "INSERT INTO customers (name, phone, credit_limit_paise, active, created_at) VALUES (?, ?, ?, ?, ?)",
                    (c_name, c_phone, c_lim, c_act, now_utc_iso),
                )
                cust_map[c_name] = int(c_cur.lastrowid)

            c1_id = cust_map["Ramesh Kumar"]
            c2_id = cust_map["Sunita Sharma"]
            c3_id = cust_map["Amit Patel"]
            c5_id = cust_map["Priya Nair"]
            c6_id = cust_map["Rajesh Gupta"]
            c7_id = cust_map["Ananya Iyer"]
            c8_id = cust_map["Manoj Singh"]

            products_raw = [
                ("ATTA-AASH-5KG", "Aashirvaad Superior MP Sharbati Atta 5kg", "bag", 24500, 21000, 15, 80),
                ("ATTA-AASH-10KG", "Aashirvaad Superior MP Atta 10kg", "bag", 46000, 39500, 10, 50),
                ("ATTA-FORT-5KG", "Fortune Chakki Fresh Atta 5kg", "bag", 22000, 18800, 12, 60),
                ("ATTA-PILL-1KG", "Pillsbury Chakki Fresh Atta 1kg", "bag", 5500, 4700, 20, 20),
                ("ATTA-MAID-1KG", "Rajdhani Maida 1kg", "bag", 4800, 4100, 15, 70),
                ("RICE-IGAT-1KG", "India Gate Basmati Rice Classic 1kg", "bag", 16000, 13600, 15, 15),
                ("RICE-IGAT-5KG", "India Gate Basmati Rice Feast Rozana 5kg", "bag", 48000, 41000, 10, 40),
                ("RICE-DAAW-1KG", "Daawat Rozana Super Basmati Rice 1kg", "bag", 11000, 9200, 20, 80),
                ("RICE-KOLM-5KG", "Wada Kolam Rice 5kg", "bag", 32000, 27000, 12, 50),
                ("RICE-SONA-5KG", "Buhler Sona Masoori Rice 5kg", "bag", 34000, 29000, 15, 60),
                ("DALS-TOOR-1KG", "Tata Sampann Unpolished Toor Dal 1kg", "bag", 17500, 15000, 20, 90),
                ("DALS-MOON-1KG", "Tata Sampann Unpolished Moong Dal 1kg", "bag", 14500, 12500, 18, 75),
                ("DALS-CHAN-1KG", "Tata Sampann Unpolished Chana Dal 1kg", "bag", 11500, 9800, 15, 80),
                ("DALS-URAD-1KG", "Tata Sampann Unpolished Urad Dal White 1kg", "bag", 16500, 14200, 15, 70),
                ("DALS-MASO-1KG", "Tata Sampann Masoor Dal 1kg", "bag", 12000, 10200, 15, 15),
                ("DALS-RAJM-500G", "Catch Natural Rajma Chitra 500g", "pkt", 8500, 7200, 12, 60),
                ("OIL-FORT-1L", "Fortune Sunlite Refined Sunflower Oil 1L", "pouch", 13500, 11800, 25, 90),
                ("OIL-DHAR-1L", "Dhara Kachi Ghani Mustard Oil 1L", "bottle", 15500, 13500, 20, 70),
                ("OIL-SOYA-1L", "Fortune Soya Health Refined Soyabean Oil 1L", "pouch", 12500, 10800, 20, 80),
                ("OIL-SAFF-1L", "Saffola Gold Pro Healthy Lifestyle 1L", "pouch", 17000, 14800, 15, 15),
                ("OIL-PARA-250ML", "Parachute 100% Pure Coconut Oil 250ml", "bottle", 11000, 9200, 20, 75),
                ("SALT-TATA-1KG", "Tata Salt Vacuum Evaporated Iodised 1kg", "pkt", 2800, 2400, 30, 100),
                ("SUG-MADH-1KG", "Madhur Pure & Hygienic Sugar 1kg", "bag", 5400, 4600, 30, 100),
                ("SPIC-HALD-200G", "Everest Turmeric Powder 200g", "box", 6500, 5200, 15, 60),
                ("SPIC-MIRCH-200G", "Everest Tikhalal Chilli Powder 200g", "box", 9500, 7800, 15, 15),
                ("SPIC-DHAN-200G", "Everest Coriander Powder 200g", "box", 7200, 5800, 15, 60),
                ("SPIC-GARM-100G", "Everest Garam Masala 100g", "box", 8800, 7000, 12, 50),
                ("TEA-BLBL-500G", "Brooke Bond Red Label Tea 500g", "box", 29000, 24500, 15, 70),
                ("TEA-TAJM-250G", "Brooke Bond Taj Mahal Tea 250g", "box", 19500, 16500, 12, 50),
                ("TEA-WAGH-500G", "Wagh Bakri Premium Leaf Tea 500g", "box", 28000, 23800, 15, 60),
                ("COFF-NESC-50G", "Nescafe Classic Instant Coffee Jar 50g", "jar", 18500, 15200, 12, 50),
                ("COFF-BRU-100G", "Bru Instant Coffee Pouch 100g", "pouch", 21000, 17500, 12, 55),
                ("BISC-PARL-250G", "Parle-G Gold Glucose Biscuits 250g", "pkt", 2500, 2050, 40, 120),
                ("BISC-GDAY-200G", "Britannia Good Day Cashew 200g", "pkt", 4000, 3300, 30, 80),
                ("BISC-MARI-250G", "Britannia Marie Gold 250g", "pkt", 3500, 2900, 25, 75),
                ("BISC-OR-120G", "Cadbury Oreo Vanilla Creme Biscuits 120g", "pkt", 3500, 2850, 25, 65),
                ("BISC-BOUR-150G", "Britannia Bourbon Chocolate Cream 150g", "pkt", 3000, 2450, 25, 25),
                ("MAGG-NOOD-70G", "Maggi 2-Minute Masala Noodles 70g", "pkt", 1400, 1150, 50, 120),
                ("SNAK-HALD-400G", "Haldiram Classic Bhujia Sev 400g", "pkt", 11000, 9000, 20, 60),
                ("SNAK-ALOO-400G", "Haldiram Aloo Bhujia 400g", "pkt", 11500, 9400, 20, 60),
                ("SNAK-KURK-90G", "Kurkure Masala Munch 90g", "pkt", 2000, 1600, 35, 100),
                ("SNAK-LAYS-50G", "Lay's India's Magic Masala Potato Chips 50g", "pkt", 2000, 1600, 35, 95),
                ("SOAP-DETT-125G", "Dettol Original Bathing Soap 125g", "bar", 5800, 4700, 25, 25),
                ("SOAP-LIFE-125G", "Lifebuoy Total Germ Protection Soap 125g", "bar", 3800, 3100, 25, 80),
                ("SOAP-DOVE-100G", "Dove Cream Beauty Bathing Bar 100g", "bar", 6500, 5300, 15, 60),
                ("DENT-COLG-200G", "Colgate Strong Teeth Dental Cream 200g", "tube", 11500, 9400, 20, 75),
                ("DENT-DRED-150G", "Dabur Red Ayurvedic Toothpaste 150g", "tube", 9800, 8000, 20, 60),
                ("HAIR-HANDS-180ML", "Head & Shoulders Anti-Dandruff 180ml", "bottle", 18000, 14800, 12, 45),
                ("DET-SURF-1KG", "Surf Excel Quick Wash Detergent Powder 1kg", "bag", 14500, 12200, 20, 70),
                ("DET-ARIL-1KG", "Ariel Matic Front Load Detergent 1kg", "bag", 26000, 21800, 15, 50),
                ("DISH-VIM-300G", "Vim Dishwash Bar 300g", "bar", 2500, 2000, 30, 100),
                ("DISH-VLIM-500ML", "Vim Lemon Dishwash Gel Bottle 500ml", "bottle", 12000, 9800, 15, 60),
                ("CLN-LIZL-500ML", "Lizol Disinfectant Floor Cleaner Citrus 500ml", "bottle", 11500, 9500, 15, 65),
                ("CLN-HARP-500ML", "Harpic Power Plus Toilet Cleaner 500ml", "bottle", 9800, 8100, 15, 0),
                ("DAIR-AMUL-500G", "Amul Butter Pasteurized 500g", "pack", 27500, 24500, 12, 40),
                ("DAIR-AMUL-100G", "Amul Butter Pasteurized 100g", "pack", 5800, 5100, 20, 60),
                ("DAIR-CHEE-200G", "Amul Processed Cheese Slices 200g", "pack", 14500, 12500, 12, 45),
                ("DAIR-PANE-200G", "Amul Fresh Paneer 200g", "pack", 9000, 7800, 15, 50),
                ("DAIR-MILK-1L", "Amul Taaza Homogenised Toned Milk 1L", "tetrapack", 7200, 6300, 25, 25),
                ("DAIR-NEST-400G", "Nestle Everyday Dairy Whitener 400g", "pouch", 23500, 20200, 10, 0),
            ]

            thirty_days_ago_dt = now_k - timedelta(days=30)
            thirty_days_ago_utc_iso = thirty_days_ago_dt.astimezone(timezone.utc).isoformat()

            prod_map: dict[str, int] = {}
            prod_info: dict[int, dict[str, int]] = {}

            for sku, name, unit, price, cost, reorder, open_qty in products_raw:
                p_cur = conn.execute(
                    "INSERT INTO products (sku, name, unit, price_paise, cost_paise, reorder_level, active, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                    (sku, name, unit, price, cost, reorder, thirty_days_ago_utc_iso),
                )
                pid = int(p_cur.lastrowid)
                prod_map[sku] = pid
                prod_info[pid] = {
                    "price": price,
                    "cost": cost,
                    "reorder": reorder,
                }
                if open_qty > 0:
                    conn.execute(
                        "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) "
                        "VALUES (?, ?, 'opening', NULL, NULL, ?, 'Initial opening stock', ?)",
                        (pid, open_qty, owner_id, thirty_days_ago_utc_iso),
                    )

            po1_created_iso = (now_k - timedelta(days=25)).astimezone(timezone.utc).isoformat()
            po1_sent_iso = (now_k - timedelta(days=24)).astimezone(timezone.utc).isoformat()
            po1_received_iso = (now_k - timedelta(days=22)).astimezone(timezone.utc).isoformat()

            po1_cur = conn.execute(
                "INSERT INTO purchase_orders (supplier_id, status, created_by, created_at, sent_at, received_at) "
                "VALUES (?, 'received', ?, ?, ?, ?)",
                (sup1_id, owner_id, po1_created_iso, po1_sent_iso, po1_received_iso),
            )
            po1_id = int(po1_cur.lastrowid)

            p_salt = prod_map["SALT-TATA-1KG"]
            p_sugar = prod_map["SUG-MADH-1KG"]

            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) VALUES (?, ?, 50, 50, 2400)",
                (po1_id, p_salt),
            )
            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) VALUES (?, ?, 50, 50, 4600)",
                (po1_id, p_sugar),
            )
            conn.execute(
                "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, 50, 'delivery', 'purchase_order', ?, ?, 'Receipt for PO', ?)",
                (p_salt, po1_id, owner_id, po1_received_iso),
            )
            conn.execute(
                "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, 50, 'delivery', 'purchase_order', ?, ?, 'Receipt for PO', ?)",
                (p_sugar, po1_id, owner_id, po1_received_iso),
            )

            po2_created_iso = (now_k - timedelta(days=10)).astimezone(timezone.utc).isoformat()
            po2_sent_iso = (now_k - timedelta(days=9)).astimezone(timezone.utc).isoformat()
            po2_partial_iso = (now_k - timedelta(days=8)).astimezone(timezone.utc).isoformat()

            po2_cur = conn.execute(
                "INSERT INTO purchase_orders (supplier_id, status, created_by, created_at, sent_at, received_at) "
                "VALUES (?, 'partially_received', ?, ?, ?, NULL)",
                (sup2_id, owner_id, po2_created_iso, po2_sent_iso),
            )
            po2_id = int(po2_cur.lastrowid)

            p_atta5 = prod_map["ATTA-AASH-5KG"]
            p_rice5 = prod_map["RICE-IGAT-5KG"]

            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) VALUES (?, ?, 40, 25, 21000)",
                (po2_id, p_atta5),
            )
            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) VALUES (?, ?, 20, 0, 41000)",
                (po2_id, p_rice5),
            )
            conn.execute(
                "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, 25, 'delivery', 'purchase_order', ?, ?, 'Partial receipt for PO', ?)",
                (p_atta5, po2_id, owner_id, po2_partial_iso),
            )

            po3_created_iso = (now_k - timedelta(days=3)).astimezone(timezone.utc).isoformat()
            po3_sent_iso = (now_k - timedelta(days=2)).astimezone(timezone.utc).isoformat()

            po3_cur = conn.execute(
                "INSERT INTO purchase_orders (supplier_id, status, created_by, created_at, sent_at, received_at) "
                "VALUES (?, 'sent', ?, ?, ?, NULL)",
                (sup3_id, owner_id, po3_created_iso, po3_sent_iso),
            )
            po3_id = int(po3_cur.lastrowid)

            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) VALUES (?, ?, 60, 0, 3100)",
                (po3_id, prod_map["SOAP-LIFE-125G"]),
            )
            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) VALUES (?, ?, 40, 0, 9400)",
                (po3_id, prod_map["DENT-COLG-200G"]),
            )

            po4_created_iso = (now_k - timedelta(days=1)).astimezone(timezone.utc).isoformat()
            po4_cur = conn.execute(
                "INSERT INTO purchase_orders (supplier_id, status, created_by, created_at, sent_at, received_at) "
                "VALUES (?, 'draft', ?, ?, NULL, NULL)",
                (sup1_id, owner_id, po4_created_iso),
            )
            po4_id = int(po4_cur.lastrowid)

            conn.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, qty_ordered, qty_received, unit_cost_paise) VALUES (?, ?, 100, 0, 1150)",
                (po4_id, prod_map["MAGG-NOOD-70G"]),
            )

            audit_dt1 = (now_k - timedelta(days=15)).astimezone(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_value, new_value, created_at) VALUES (?, 'update', 'product', ?, ?, ?, ?)",
                (
                    owner_id,
                    p_salt,
                    json.dumps({"price_paise": 2600, "cost_paise": 2400}),
                    json.dumps({"price_paise": 2800, "cost_paise": 2400}),
                    audit_dt1,
                ),
            )

            audit_dt2 = (now_k - timedelta(days=12)).astimezone(timezone.utc).isoformat()
            p_maggi = prod_map["MAGG-NOOD-70G"]
            conn.execute(
                "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, -2, 'adjustment', NULL, NULL, ?, 'Damaged packaging during shelf stocking', ?)",
                (p_maggi, owner_id, audit_dt2),
            )
            conn.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_value, new_value, created_at) VALUES (?, 'adjustment', 'stock', ?, ?, ?, ?)",
                (
                    owner_id,
                    p_maggi,
                    json.dumps({"current_stock": 118}),
                    json.dumps({"current_stock": 116, "qty_change": -2, "reason": "Damaged packaging during shelf stocking"}),
                    audit_dt2,
                ),
            )

            audit_dt3 = (now_k - timedelta(days=6)).astimezone(timezone.utc).isoformat()
            p_parle = prod_map["BISC-PARL-250G"]
            conn.execute(
                "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, 5, 'adjustment', NULL, NULL, ?, 'Physical stock count correction', ?)",
                (p_parle, owner_id, audit_dt3),
            )
            conn.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_value, new_value, created_at) VALUES (?, 'adjustment', 'stock', ?, ?, ?, ?)",
                (
                    owner_id,
                    p_parle,
                    json.dumps({"current_stock": 115}),
                    json.dumps({"current_stock": 120, "qty_change": 5, "reason": "Physical stock count correction"}),
                    audit_dt3,
                ),
            )

            low_stock_plan = {
                prod_map["SPIC-MIRCH-200G"]: 11,
                prod_map["SOAP-DETT-125G"]: 20,
                prod_map["ATTA-PILL-1KG"]: 14,
                prod_map["RICE-IGAT-1KG"]: 12,
                prod_map["DALS-MASO-1KG"]: 10,
                prod_map["OIL-SAFF-1L"]: 8,
            }

            excluded_from_sales = {
                prod_map["CLN-HARP-500ML"],
                prod_map["DAIR-NEST-400G"],
                prod_map["DAIR-MILK-1L"],
                prod_map["BISC-BOUR-150G"],
            }
            excluded_from_sales.update(low_stock_plan.keys())

            healthy_pool = [pid for pid in prod_info if pid not in excluded_from_sales]

            rng = random.Random(42)

            low_stock_units_remaining = dict(low_stock_plan)

            def make_sale(
                sale_time_iso: str,
                user_id: int,
                payment_type: str,
                customer_id: int | None,
                lines: list[tuple[int, int]],
            ) -> tuple[int, list[tuple[int, int, int]]]:
                total_paise = 0
                for pid, qty in lines:
                    total_paise += qty * prod_info[pid]["price"]

                s_cur = conn.execute(
                    "INSERT INTO sales (customer_id, user_id, payment_type, total_paise, created_at) VALUES (?, ?, ?, ?, ?)",
                    (customer_id, user_id, payment_type, total_paise, sale_time_iso),
                )
                sale_id = int(s_cur.lastrowid)

                created_items: list[tuple[int, int, int]] = []
                for pid, qty in lines:
                    unit_p = prod_info[pid]["price"]
                    unit_c = prod_info[pid]["cost"]
                    line_tot = qty * unit_p
                    si_cur = conn.execute(
                        "INSERT INTO sale_items (sale_id, product_id, qty, unit_price_paise, unit_cost_paise, line_total_paise) VALUES (?, ?, ?, ?, ?, ?)",
                        (sale_id, pid, qty, unit_p, unit_c, line_tot),
                    )
                    si_id = int(si_cur.lastrowid)
                    created_items.append((si_id, pid, qty))
                    conn.execute(
                        "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, ?, 'sale', 'sale', ?, ?, 'Sale', ?)",
                        (pid, -qty, sale_id, user_id, sale_time_iso),
                    )

                if payment_type == "credit" and customer_id is not None:
                    conn.execute(
                        "INSERT INTO credit_entries (customer_id, kind, amount_paise, sale_id, user_id, note, created_at) VALUES (?, 'credit_sale', ?, ?, ?, 'Credit sale', ?)",
                        (customer_id, total_paise, sale_id, user_id, sale_time_iso),
                    )

                return sale_id, created_items

            def make_return(
                sale_id: int,
                sale_item_id: int,
                product_id: int,
                qty: int,
                user_id: int,
                customer_id: int | None,
                is_credit: bool,
                return_time_iso: str,
            ) -> None:
                refund = qty * prod_info[product_id]["price"]
                r_cur = conn.execute(
                    "INSERT INTO returns (sale_id, user_id, refund_paise, created_at) VALUES (?, ?, ?, ?)",
                    (sale_id, user_id, refund, return_time_iso),
                )
                ret_id = int(r_cur.lastrowid)
                conn.execute(
                    "INSERT INTO return_items (return_id, sale_item_id, qty) VALUES (?, ?, ?)",
                    (ret_id, sale_item_id, qty),
                )
                conn.execute(
                    "INSERT INTO stock_movements (product_id, qty_change, kind, ref_type, ref_id, user_id, note, created_at) VALUES (?, ?, 'return', 'return', ?, ?, 'Sale return', ?)",
                    (product_id, qty, ret_id, user_id, return_time_iso),
                )
                if is_credit and customer_id is not None:
                    conn.execute(
                        "INSERT INTO credit_entries (customer_id, kind, amount_paise, sale_id, user_id, note, created_at) VALUES (?, 'return', ?, ?, ?, 'Return credit', ?)",
                        (customer_id, -refund, sale_id, user_id, return_time_iso),
                    )

            def make_payment(customer_id: int, amount_paise: int, user_id: int, payment_time_iso: str) -> None:
                conn.execute(
                    "INSERT INTO credit_entries (customer_id, kind, amount_paise, sale_id, user_id, note, created_at) VALUES (?, 'payment', ?, NULL, ?, 'Payment towards udhaar', ?)",
                    (customer_id, -amount_paise, user_id, payment_time_iso),
                )

            recorded_sales: dict[str, tuple[int, list[tuple[int, int, int]]]] = {}

            for day_offset in range(29, -1, -1):
                day_date = today_date - timedelta(days=day_offset)
                is_weekend = day_date.weekday() in (5, 6)

                num_sales = rng.randint(6, 8) if is_weekend else rng.randint(4, 5)

                times: list[tuple[int, int]] = []
                if day_offset == 15:
                    times.append((23, 59))
                if day_offset == 14:
                    times.append((0, 1))

                while len(times) < num_sales:
                    if rng.random() < 0.65:
                        h = rng.randint(17, 21)
                    else:
                        h = rng.randint(8, 16)
                    m = rng.randint(0, 59)
                    if (h, m) not in times:
                        times.append((h, m))

                times.sort()

                for h, m in times:
                    s_dt = datetime(day_date.year, day_date.month, day_date.day, h, m, rng.randint(0, 59), tzinfo=kolkata_tz)
                    s_iso = s_dt.astimezone(timezone.utc).isoformat()
                    u_id = rng.choice(user_pool)

                    basket_size = rng.randint(1, 5)
                    selected_prods = rng.sample(healthy_pool, basket_size)
                    sale_lines: list[tuple[int, int]] = []
                    for sp in selected_prods:
                        qty = rng.randint(1, 2)
                        sale_lines.append((sp, qty))

                    sid, items = make_sale(s_iso, u_id, "cash", None, sale_lines)
                    key = f"day_{day_offset}_{h}_{m}"
                    recorded_sales[key] = (sid, items)

                for lpid, lqty in list(low_stock_units_remaining.items()):
                    if lqty > 0 and (day_offset % 5 == 0 or lqty > (day_offset // 2)):
                        sold_chunk = min(lqty, rng.randint(1, 3))
                        low_stock_units_remaining[lpid] -= sold_chunk
                        s_dt = datetime(day_date.year, day_date.month, day_date.day, 18, rng.randint(10, 50), 30, tzinfo=kolkata_tz)
                        u_id = rng.choice(user_pool)
                        make_sale(s_dt.astimezone(timezone.utc).isoformat(), u_id, "cash", None, [(lpid, sold_chunk)])

            for lpid, remaining_qty in low_stock_units_remaining.items():
                if remaining_qty > 0:
                    s_dt = datetime(today_date.year, today_date.month, today_date.day, 12, 30, 0, tzinfo=kolkata_tz)
                    make_sale(s_dt.astimezone(timezone.utc).isoformat(), owner_id, "cash", None, [(lpid, remaining_qty)])

            c1_s1_dt = datetime.combine(today_date - timedelta(days=26), datetime.min.time().replace(hour=17, minute=15), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c1_s1_dt, owner_id, "credit", c1_id, [(prod_map["OIL-FORT-1L"], 2), (prod_map["SNAK-HALD-400G"], 1)])

            c1_p1_dt = datetime.combine(today_date - timedelta(days=20), datetime.min.time().replace(hour=11, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c1_id, 15000, staff_id, c1_p1_dt)

            c1_s2_dt = datetime.combine(today_date - timedelta(days=15), datetime.min.time().replace(hour=19, minute=30), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c1_s2_dt, staff2_id, "credit", c1_id, [(prod_map["OIL-FORT-1L"], 2), (prod_map["TEA-BLBL-500G"], 1)])

            c1_p2_dt = datetime.combine(today_date - timedelta(days=10), datetime.min.time().replace(hour=10, minute=30), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c1_id, 20000, owner_id, c1_p2_dt)

            c1_s3_dt = datetime.combine(today_date - timedelta(days=2), datetime.min.time().replace(hour=20, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c1_s3_dt, staff_id, "credit", c1_id, [(prod_map["OIL-FORT-1L"], 1), (prod_map["DALS-TOOR-1KG"], 1)])

            c2_s1_dt = datetime.combine(today_date - timedelta(days=22), datetime.min.time().replace(hour=18, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c2_s1_dt, staff_id, "credit", c2_id, [(prod_map["OIL-FORT-1L"], 1), (prod_map["DALS-TOOR-1KG"], 1)])

            c2_s2_dt = datetime.combine(today_date - timedelta(days=18), datetime.min.time().replace(hour=19, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c2_s2_dt, owner_id, "credit", c2_id, [(prod_map["TEA-BLBL-500G"], 1)])

            c2_p1_dt = datetime.combine(today_date - timedelta(days=12), datetime.min.time().replace(hour=11, minute=45), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c2_id, 60000, staff2_id, c2_p1_dt)

            c3_s1_dt = datetime.combine(today_date - timedelta(days=20), datetime.min.time().replace(hour=16, minute=30), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            c3_sale_id, c3_sale_items = make_sale(c3_s1_dt, staff_id, "credit", c3_id, [(prod_map["SNAK-HALD-400G"], 1)])

            c3_p1_dt = datetime.combine(today_date - timedelta(days=16), datetime.min.time().replace(hour=10, minute=15), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c3_id, 11000, owner_id, c3_p1_dt)

            c3_ret_dt = datetime.combine(today_date - timedelta(days=10), datetime.min.time().replace(hour=15, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_return(
                sale_id=c3_sale_id,
                sale_item_id=c3_sale_items[0][0],
                product_id=c3_sale_items[0][1],
                qty=1,
                user_id=owner_id,
                customer_id=c3_id,
                is_credit=True,
                return_time_iso=c3_ret_dt,
            )

            c5_s1_dt = datetime.combine(today_date - timedelta(days=25), datetime.min.time().replace(hour=17, minute=45), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c5_s1_dt, staff2_id, "credit", c5_id, [(prod_map["DALS-TOOR-1KG"], 2), (prod_map["TEA-BLBL-500G"], 1)])

            c5_p1_dt = datetime.combine(today_date - timedelta(days=19), datetime.min.time().replace(hour=12, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c5_id, 35000, owner_id, c5_p1_dt)

            c5_s2_dt = datetime.combine(today_date - timedelta(days=13), datetime.min.time().replace(hour=18, minute=30), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c5_s2_dt, staff_id, "credit", c5_id, [(prod_map["DALS-TOOR-1KG"], 3), (prod_map["SNAK-HALD-400G"], 2)])

            c5_p2_dt = datetime.combine(today_date - timedelta(days=7), datetime.min.time().replace(hour=11, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c5_id, 40000, staff2_id, c5_p2_dt)

            c5_s3_dt = datetime.combine(today_date - timedelta(days=3), datetime.min.time().replace(hour=19, minute=15), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c5_s3_dt, owner_id, "credit", c5_id, [(prod_map["OIL-FORT-1L"], 2), (prod_map["SNAK-HALD-400G"], 1)])

            c6_s1_dt = datetime.combine(today_date - timedelta(days=23), datetime.min.time().replace(hour=18, minute=20), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c6_s1_dt, staff_id, "credit", c6_id, [(prod_map["OIL-FORT-1L"], 3), (prod_map["SNAK-HALD-400G"], 1)])

            c6_p1_dt = datetime.combine(today_date - timedelta(days=17), datetime.min.time().replace(hour=10, minute=45), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c6_id, 25000, owner_id, c6_p1_dt)

            c6_s2_dt = datetime.combine(today_date - timedelta(days=8), datetime.min.time().replace(hour=20, minute=10), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c6_s2_dt, staff2_id, "credit", c6_id, [(prod_map["TEA-BLBL-500G"], 1)])

            c7_s1_dt = datetime.combine(today_date - timedelta(days=27), datetime.min.time().replace(hour=16, minute=50), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c7_s1_dt, owner_id, "credit", c7_id, [(prod_map["TEA-BLBL-500G"], 2), (prod_map["DALS-TOOR-1KG"], 3)])

            c7_p1_dt = datetime.combine(today_date - timedelta(days=21), datetime.min.time().replace(hour=11, minute=30), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c7_id, 50000, staff_id, c7_p1_dt)

            c7_s2_dt = datetime.combine(today_date - timedelta(days=11), datetime.min.time().replace(hour=19, minute=40), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c7_s2_dt, staff2_id, "credit", c7_id, [(prod_map["OIL-FORT-1L"], 4), (prod_map["DALS-TOOR-1KG"], 4)])

            c7_p2_dt = datetime.combine(today_date - timedelta(days=5), datetime.min.time().replace(hour=12, minute=15), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c7_id, 40000, owner_id, c7_p2_dt)

            c8_s1_dt = datetime.combine(today_date - timedelta(days=17), datetime.min.time().replace(hour=17, minute=30), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_sale(c8_s1_dt, staff_id, "credit", c8_id, [(prod_map["OIL-FORT-1L"], 2), (prod_map["SNAK-HALD-400G"], 1)])

            c8_p1_dt = datetime.combine(today_date - timedelta(days=9), datetime.min.time().replace(hour=10, minute=0), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_payment(c8_id, 15000, owner_id, c8_p1_dt)

            ret1_sale_dt = datetime.combine(today_date - timedelta(days=20), datetime.min.time().replace(hour=14, minute=10), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            ret1_sid, ret1_items = make_sale(ret1_sale_dt, staff_id, "cash", None, [(prod_map["MAGG-NOOD-70G"], 2)])
            ret1_dt = datetime.combine(today_date - timedelta(days=18), datetime.min.time().replace(hour=11, minute=20), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_return(ret1_sid, ret1_items[0][0], ret1_items[0][1], 1, staff_id, None, False, ret1_dt)

            ret2_sale_dt = datetime.combine(today_date - timedelta(days=6), datetime.min.time().replace(hour=13, minute=40), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            ret2_sid, ret2_items = make_sale(ret2_sale_dt, staff2_id, "cash", None, [(prod_map["BISC-PARL-250G"], 3)])
            ret2_dt = datetime.combine(today_date - timedelta(days=4), datetime.min.time().replace(hour=16, minute=15), tzinfo=kolkata_tz).astimezone(timezone.utc).isoformat()
            make_return(ret2_sid, ret2_items[0][0], ret2_items[0][1], 1, owner_id, None, False, ret2_dt)

        prod_count = conn.execute("SELECT COUNT(*) AS total FROM products").fetchone()["total"]
        cust_count = conn.execute("SELECT COUNT(*) AS total FROM customers").fetchone()["total"]
        sales_count = conn.execute("SELECT COUNT(*) AS total FROM sales").fetchone()["total"]

        low_stock_row = conn.execute(
            "SELECT COUNT(*) AS total FROM stock_levels sl JOIN products p ON sl.product_id = p.id WHERE sl.current_stock < p.reorder_level"
        ).fetchone()
        low_stock_count = low_stock_row["total"]

        udhaar_row = conn.execute(
            "SELECT COALESCE(SUM(amount_paise), 0) AS total_paise FROM credit_entries"
        ).fetchone()
        udhaar_paise = udhaar_row["total_paise"]
        udhaar_rs = udhaar_paise / 100.0

        sys.stdout.write("Database seeded successfully!\n")
        sys.stdout.write("Summary:\n")
        sys.stdout.write(f"  Products: {prod_count}\n")
        sys.stdout.write(f"  Low-stock items: {low_stock_count}\n")
        sys.stdout.write(f"  Customers: {cust_count}\n")
        sys.stdout.write(f"  Sales: {sales_count}\n")
        sys.stdout.write(f"  Total outstanding udhaar: Rs {udhaar_rs:.2f}\n")
        sys.stdout.write("Credentials:\n")
        sys.stdout.write("  Owner user: username='owner', password='owner123'\n")
        sys.stdout.write("  Staff user: username='staff', password='staff123'\n")
        sys.stdout.write("  Staff user 2: username='staff2', password='staff123'\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
