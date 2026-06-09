-- ============================================================================
-- source-db : static reference data (categories + merchants)
-- ----------------------------------------------------------------------------
-- Runs once at DB init, after 01-schema.sql. The mock-data generator reads
-- these tables to assign categories/merchants to generated transactions, so
-- this file is the single source of truth for the taxonomy.
-- ============================================================================

SET search_path TO core;

-- ---------------------------------------------------------------------------
-- categories : top-level groups first (NULL parent), then leaves.
-- ---------------------------------------------------------------------------
INSERT INTO categories (category_id, name, parent_category_id, kind) VALUES
    -- expense groups
    (1,  'Housing',           NULL, 'expense'),
    (2,  'Food',              NULL, 'expense'),
    (3,  'Transport',         NULL, 'expense'),
    (4,  'Shopping',          NULL, 'expense'),
    (5,  'Entertainment',     NULL, 'expense'),
    (6,  'Health',            NULL, 'expense'),
    (7,  'Travel',            NULL, 'expense'),
    (8,  'Bills & Utilities', NULL, 'expense'),
    (9,  'Education',         NULL, 'expense'),
    (10, 'Other',             NULL, 'expense'),
    -- income group
    (50, 'Income',            NULL, 'income');

INSERT INTO categories (category_id, name, parent_category_id, kind) VALUES
    -- Housing
    (101, 'Rent',                1, 'expense'),
    (102, 'Mortgage',            1, 'expense'),
    (103, 'Home Maintenance',    1, 'expense'),
    -- Food
    (201, 'Groceries',           2, 'expense'),
    (202, 'Dining Out',          2, 'expense'),
    (203, 'Coffee',              2, 'expense'),
    -- Transport
    (301, 'Fuel',                3, 'expense'),
    (302, 'Public Transport',    3, 'expense'),
    (303, 'Ride Share',          3, 'expense'),
    (304, 'Parking',             3, 'expense'),
    -- Shopping
    (401, 'Clothing',            4, 'expense'),
    (402, 'Electronics',         4, 'expense'),
    (403, 'General Merchandise', 4, 'expense'),
    -- Entertainment
    (501, 'Streaming',           5, 'expense'),
    (502, 'Events',              5, 'expense'),
    (503, 'Gaming',              5, 'expense'),
    -- Health
    (601, 'Pharmacy',            6, 'expense'),
    (602, 'Fitness',             6, 'expense'),
    (603, 'Medical',             6, 'expense'),
    -- Travel
    (701, 'Flights',             7, 'expense'),
    (702, 'Hotels',              7, 'expense'),
    (703, 'Car Rental',          7, 'expense'),
    -- Bills & Utilities
    (801, 'Electricity',         8, 'expense'),
    (802, 'Water',               8, 'expense'),
    (803, 'Internet',            8, 'expense'),
    (804, 'Mobile',              8, 'expense'),
    (805, 'Insurance',           8, 'expense'),
    -- Education
    (901, 'Tuition',             9, 'expense'),
    (902, 'Books',               9, 'expense'),
    (903, 'Courses',             9, 'expense'),
    -- Other
    (1001, 'Cash Withdrawal',   10, 'expense'),
    (1002, 'Fees',              10, 'expense'),
    (1003, 'Misc',              10, 'expense'),
    -- Income
    (5001, 'Salary',            50, 'income'),
    (5002, 'Freelance',         50, 'income'),
    (5003, 'Investment Income', 50, 'income'),
    (5004, 'Refund',            50, 'income'),
    (5005, 'Interest',          50, 'income');

-- ---------------------------------------------------------------------------
-- merchants : map to the leaf category they usually belong to.
-- ---------------------------------------------------------------------------
INSERT INTO merchants (merchant_id, name, default_category_id) VALUES
    (1,  'Whole Foods',       201),
    (2,  'Trader Joe''s',     201),
    (3,  'Costco',            201),
    (4,  'Aldi',              201),
    (5,  'McDonald''s',       202),
    (6,  'Chipotle',          202),
    (7,  'Pizza Hut',         202),
    (8,  'Olive Garden',      202),
    (9,  'Starbucks',         203),
    (10, 'Dunkin',            203),
    (11, 'Shell',             301),
    (12, 'BP',                301),
    (13, 'Exxon',             301),
    (14, 'Metro Transit',     302),
    (15, 'Uber',              303),
    (16, 'Lyft',              303),
    (17, 'Zara',              401),
    (18, 'H&M',               401),
    (19, 'Nike',              401),
    (20, 'Best Buy',          402),
    (21, 'Apple Store',       402),
    (22, 'Amazon',            403),
    (23, 'Walmart',           403),
    (24, 'Target',            403),
    (25, 'Netflix',           501),
    (26, 'Spotify',           501),
    (27, 'Disney+',           501),
    (28, 'YouTube Premium',   501),
    (29, 'Ticketmaster',      502),
    (30, 'Steam',             503),
    (31, 'PlayStation Store', 503),
    (32, 'CVS',               601),
    (33, 'Walgreens',         601),
    (34, 'Planet Fitness',    602),
    (35, 'Delta',             701),
    (36, 'United',            701),
    (37, 'Marriott',          702),
    (38, 'Hilton',            702),
    (39, 'Airbnb',            702),
    (40, 'Comcast',           803),
    (41, 'Verizon',           804),
    (42, 'AT&T',              804),
    (43, 'City Power Co',     801);
