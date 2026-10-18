# GourmetGrove - Complete ER Diagram with Attributes and Relationships

```mermaid
erDiagram
    %% User Module
    USER {
        bigint id PK
        string username UK
        string email UK
        string password
        string first_name
        string last_name
        bool is_staff
        bool is_active
        datetime date_joined
    }

    USER_PROFILE {
        bigint id PK
        bigint user_id FK "1:1 with USER"
        string profile_picture
        date birth_date
        string phone_number
    }

    USER_ADDRESS {
        bigint id PK
        bigint user_id FK "N:1 with USER"
        string address_line1
        string address_line2
        string city
        string state
        string postal_code
        string country
        bool is_default
    }

    %% Product Module
    CATEGORY {
        bigint id PK
        string name
        string description
        string slug UK
    }

    BRAND {
        bigint id PK
        string name
        string description
        string logo
        string website
    }

    CHOCOLATE {
        bigint id PK
        bigint category_id FK "N:1 with CATEGORY"
        bigint brand_id FK "N:1 with BRAND"
        string name
        string description
        decimal price
        decimal weight
        string ingredients
        bool is_available
        datetime created_at
        datetime updated_at
    }

    %% Order Module
    ORDER {
        bigint id PK
        bigint user_id FK "N:1 with USER"
        bigint address_id FK "N:1 with USER_ADDRESS"
        string order_number UK
        decimal total_amount
        string payment_status
        string order_status
        datetime order_date
        datetime delivery_date
        string shipping_method
    }

    ORDER_ITEM {
        bigint id PK
        bigint order_id FK "N:1 with ORDER"
        bigint chocolate_id FK "N:1 with CHOCOLATE"
        int quantity
        decimal unit_price
        decimal subtotal
    }

    %% Cart and Wishlist
    CART_ITEM {
        bigint id PK
        bigint user_id FK "N:1 with USER"
        bigint chocolate_id FK "N:1 with CHOCOLATE"
        int quantity
        datetime added_at
    }

    WISHLIST_ITEM {
        bigint id PK
        bigint user_id FK "N:1 with USER"
        bigint chocolate_id FK "N:1 with CHOCOLATE"
        datetime added_at
    }

    %% Delivery Module
    DELIVERY_AGENT {
        bigint id PK
        bigint user_id FK "1:1 with USER"
        bigint store_location_id FK "N:1 with STORE_LOCATION"
        bigint assigned_vehicle_id FK "1:1 with VEHICLE"
        bool is_available
        decimal rating
    }

    VEHICLE {
        bigint id PK
        string vehicle_number UK
        string vehicle_type
        string model
        string color
    }

    STORE_LOCATION {
        bigint id PK
        string name
        string address
        string city
        string state
        string phone_number
        bool is_active
    }

    %% Relationships with Cardinality
    USER ||--o{ USER_ADDRESS : "has"
    USER ||--|| USER_PROFILE : "has"
    USER ||--o{ ORDER : "places"
    USER ||--o{ CART_ITEM : "adds"
    USER ||--o{ WISHLIST_ITEM : "saves"
    
    CATEGORY ||--o{ CHOCOLATE : "contains"
    BRAND ||--o{ CHOCOLATE : "offers"
    
    ORDER ||--o{ ORDER_ITEM : "contains"
    ORDER_ITEM }|--|| CHOCOLATE : "references"
    
    DELIVERY_AGENT ||--|| VEHICLE : "assigned"
    STORE_LOCATION ||--o{ DELIVERY_AGENT : "employs"
    
    %% Apply styles to PK, UK, FK
    class USER id,pk
    class USER_PROFILE id,pk
    class USER_ADDRESS id,pk
    class CATEGORY id,pk
    class BRAND id,pk
    class CHOCOLATE id,pk
    class ORDER id,pk
    class ORDER_ITEM id,pk
    class CART_ITEM id,pk
    class WISHLIST_ITEM id,pk
    class DELIVERY_AGENT id,pk
    class VEHICLE id,pk
    class STORE_LOCATION id,pk
    
    class USER username,email uk
    class USER_ADDRESS id uk
    class CHOCOLATE id uk
    class ORDER order_number uk
    class VEHICLE vehicle_number uk
    
    class USER_PROFILE user_id,fk
    class USER_ADDRESS user_id,fk
    class ORDER user_id,address_id,fk
    class ORDER_ITEM order_id,chocolate_id,fk
    class CART_ITEM user_id,chocolate_id,fk
    class WISHLIST_ITEM user_id,chocolate_id,fk
    class DELIVERY_AGENT user_id,store_location_id,assigned_vehicle_id,fk
    
    %% Legend
    classDef pk fill:#f9f,stroke:#333,stroke-width:2px
    classDef uk fill:#9f9,stroke:#333,stroke-width:1px
    classDef fk fill:#bbf,stroke:#333,stroke-width:1px
```

## Legend
- **PK**: Primary Key (Pink background)
- **UK**: Unique Key (Green background)
- **FK**: Foreign Key (Blue background)
- **1:1**: One-to-One relationship
- **1:N**: One-to-Many relationship
- **N:1**: Many-to-One relationship
- **o{**: Zero or more
- **||**: Exactly one
- **}o{**: Many-to-Many (not directly used in this diagram)
