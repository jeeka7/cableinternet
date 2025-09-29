import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# --- Database Setup ---
def init_db():
    """Initializes the SQLite database and creates the customers table if it doesn't exist."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    # Removed bill_date column
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mobile TEXT,
            address TEXT,
            plan_details TEXT,
            per_month_cost REAL,
            internet_renewal_date DATE,
            pending_amount REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

# --- Database Operations ---
def add_customer(name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount):
    """Adds a new customer to the database."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    # Removed bill_date from query
    c.execute('''
        INSERT INTO customers (name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount))
    conn.commit()
    conn.close()

def get_all_customers():
    """Retrieves all customers from the database."""
    conn = sqlite3.connect('isp_payments.db')
    df = pd.read_sql_query("SELECT * FROM customers", conn)
    conn.close()
    return df

def get_customer_by_id(customer_id):
    """Retrieves a single customer by their ID."""
    conn = sqlite3.connect('isp_payments.db')
    customer = pd.read_sql_query(f"SELECT * FROM customers WHERE customer_id = {customer_id}", conn)
    conn.close()
    return customer.iloc[0] if not customer.empty else None


def update_customer(customer_id, name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount):
    """Updates an existing customer's details."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    # Removed bill_date from query
    c.execute('''
        UPDATE customers
        SET name = ?, mobile = ?, address = ?, plan_details = ?, per_month_cost = ?,
            internet_renewal_date = ?, pending_amount = ?
        WHERE customer_id = ?
    ''', (name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount, customer_id))
    conn.commit()
    conn.close()

def delete_customer(customer_id):
    """Deletes a customer from the database."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    c.execute("DELETE FROM customers WHERE customer_id = ?", (customer_id,))
    conn.commit()
    conn.close()

def record_payment(customer_id, amount_paid):
    """Records a payment for a customer and updates their pending amount."""
    customer = get_customer_by_id(customer_id)
    if customer is not None:
        new_pending_amount = customer['pending_amount'] - amount_paid
        # Also update the renewal date
        try:
            current_renewal_date = datetime.strptime(customer['internet_renewal_date'], '%Y-%m-%d').date()
            new_renewal_date = current_renewal_date + timedelta(days=30)
        except (ValueError, TypeError):
            new_renewal_date = datetime.now().date() + timedelta(days=30)

        conn = sqlite3.connect('isp_payments.db')
        c = conn.cursor()
        c.execute('''
            UPDATE customers
            SET pending_amount = ?, internet_renewal_date = ?
            WHERE customer_id = ?
        ''', (new_pending_amount, new_renewal_date, customer_id))
        conn.commit()
        conn.close()
        return True
    return False


# --- Helper function for date formatting ---
def format_df_dates(df, date_column='internet_renewal_date'):
    """Formats a DataFrame's date column to DD-MM-YYYY."""
    df_display = df.copy()
    df_display[date_column] = pd.to_datetime(df_display[date_column]).dt.strftime('%d-%m-%Y')
    return df_display

# --- Streamlit UI ---
st.set_page_config(page_title="ISP Payment Manager", layout="wide")

def main():
    """Main function to run the Streamlit app."""
    init_db()
    st.title("ISP Customer Payment Manager")

    menu = ["View Customers", "Search Customer", "Add Customer", "Update/Delete Customer", "Record Payment", "Upcoming Renewals"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "View Customers":
        st.subheader("All Customers")
        customers_df = get_all_customers()
        if not customers_df.empty:
            display_df = format_df_dates(customers_df)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No customers found. Add a customer to get started.")

    elif choice == "Search Customer":
        st.subheader("Search for a Customer")
        customers_df = get_all_customers()
        if not customers_df.empty:
            customer_id_to_search = st.number_input("Enter Customer ID to view details", min_value=1, step=1)
            if st.button("Search"):
                customer_data = get_customer_by_id(customer_id_to_search)
                if customer_data is not None:
                    st.success(f"Displaying details for Customer ID: {customer_id_to_search}")
                    # Transpose for better single-record view and format date
                    customer_df = pd.DataFrame(customer_data).transpose()
                    customer_df.columns = customer_data.index
                    display_df = format_df_dates(customer_df)
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.warning(f"No customer found with ID: {customer_id_to_search}")
        else:
            st.info("No customers in the database to search.")


    elif choice == "Add Customer":
        st.subheader("Add a New Customer")
        with st.form("add_customer_form", clear_on_submit=True):
            name = st.text_input("Name", placeholder="John Doe")
            mobile = st.text_input("Mobile Number", placeholder="9876543210")
            address = st.text_area("Address", placeholder="123 Main St, City")
            plan_details = st.text_input("Plan Details", placeholder="Unlimited 50Mbps")
            per_month_cost = st.number_input("Per Month Cost (₹)", min_value=0.0, step=50.0)
            internet_renewal_date = st.date_input("Internet Renewal Date")
            pending_amount = st.number_input("Initial Pending Amount (₹)", min_value=0.0, step=100.0)

            submitted = st.form_submit_button("Add Customer")
            if submitted:
                if name:
                    add_customer(name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount)
                    st.success(f"Customer '{name}' added successfully!")
                else:
                    st.warning("Customer name is required.")

    elif choice == "Update/Delete Customer":
        st.subheader("Update or Delete Customer Information")
        customers_df = get_all_customers()
        if not customers_df.empty:
            customer_list = [f"{row['customer_id']} - {row['name']}" for index, row in customers_df.iterrows()]
            selected_customer_str = st.selectbox("Select a Customer", customer_list)

            if selected_customer_str:
                selected_customer_id = int(selected_customer_str.split(" - ")[0])
                customer_data = get_customer_by_id(selected_customer_id)

                with st.form("update_customer_form"):
                    st.write(f"**Editing Customer ID:** {customer_data['customer_id']}")
                    name = st.text_input("Name", value=customer_data['name'])
                    mobile = st.text_input("Mobile Number", value=customer_data['mobile'])
                    address = st.text_area("Address", value=customer_data['address'])
                    plan_details = st.text_input("Plan Details", value=customer_data['plan_details'])
                    per_month_cost = st.number_input("Per Month Cost (₹)", min_value=0.0, step=50.0, value=float(customer_data['per_month_cost']))

                    try:
                        renewal_date_val = datetime.strptime(customer_data['internet_renewal_date'], '%Y-%m-%d').date()
                    except (TypeError, ValueError):
                        renewal_date_val = datetime.now().date()

                    internet_renewal_date = st.date_input("Internet Renewal Date", value=renewal_date_val)
                    pending_amount = st.number_input("Pending Amount (₹)", min_value=0.0, step=100.0, value=float(customer_data['pending_amount']))

                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button("Update Customer")
                    with col2:
                        delete_button = st.form_submit_button("Delete Customer")

                    if update_button:
                        update_customer(selected_customer_id, name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount)
                        st.success(f"Customer ID {selected_customer_id} updated successfully!")

                    if delete_button:
                        delete_customer(selected_customer_id)
                        st.warning(f"Customer ID {selected_customer_id} has been deleted.")
                        st.rerun()

    elif choice == "Record Payment":
        st.subheader("Record a Customer Payment")
        customers_df = get_all_customers()
        if not customers_df.empty:
            customer_list = [f"{row['customer_id']} - {row['name']} (Pending: ₹{row['pending_amount']})" for index, row in customers_df.iterrows()]
            selected_customer_str = st.selectbox("Select a Customer", customer_list)

            if selected_customer_str:
                selected_customer_id = int(selected_customer_str.split(" - ")[0])

                with st.form("payment_form", clear_on_submit=True):
                    amount_paid = st.number_input("Amount Paid (₹)", min_value=0.01, step=50.0)
                    payment_button = st.form_submit_button("Record Payment")

                    if payment_button:
                        if record_payment(selected_customer_id, amount_paid):
                            st.success(f"Payment of ₹{amount_paid} recorded for Customer ID {selected_customer_id}. Renewal date and pending amount updated.")
                        else:
                            st.error("Failed to record payment.")

    elif choice == "Upcoming Renewals":
        st.subheader("Upcoming Renewals")
        customers_df = get_all_customers()
        if not customers_df.empty:
            try:
                customers_df['internet_renewal_date'] = pd.to_datetime(customers_df['internet_renewal_date'])
                today = pd.Timestamp.now().floor('D') # Use pandas Timestamp for comparison
                next_10_days = today + timedelta(days=10)

                upcoming_renewals = customers_df[
                    (customers_df['internet_renewal_date'] >= today) &
                    (customers_df['internet_renewal_date'] <= next_10_days)
                ].sort_values(by='internet_renewal_date')

                st.write("Renewals in the next 10 days:")
                if not upcoming_renewals.empty:
                    display_upcoming = format_df_dates(upcoming_renewals)
                    st.dataframe(display_upcoming, use_container_width=True, hide_index=True)
                else:
                    st.info("No upcoming renewals in the next 10 days.")

                past_due = customers_df[customers_df['internet_renewal_date'] < today].sort_values(by='internet_renewal_date')
                st.write("Past Due Renewals:")
                if not past_due.empty:
                    display_past_due = format_df_dates(past_due)
                    st.dataframe(display_past_due, use_container_width=True, hide_index=True)
                else:
                    st.info("No customers with past due renewals.")


            except Exception as e:
                st.error(f"An error occurred while processing dates: {e}")
        else:
            st.info("No customers found.")


if __name__ == '__main__':
    main()

