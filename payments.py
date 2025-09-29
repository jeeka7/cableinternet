import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
import base64

# --- PDF Generation ---
class PDF(FPDF):
    def header(self):
        # Set up a logo or title
        self.set_font('Helvetica', 'B', 15)
        self.cell(0, 10, 'Customer Pending Amount Report', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        # Page numbers in the footer
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(df):
    """Generates a PDF report from a dataframe of customers."""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 12)
    
    # Table Header - Added Customer ID and adjusted widths
    pdf.cell(30, 10, 'Cust. ID', 1, 0, 'C')
    pdf.cell(100, 10, 'Customer Name', 1, 0, 'C')
    pdf.cell(60, 10, 'Pending Amount (Rs)', 1, 1, 'C')
    
    pdf.set_font('Helvetica', '', 11)
    # Table Body
    for index, row in df.iterrows():
        # Sanitize name for the PDF's default font encoding (latin-1) to prevent errors
        name = str(row['name']).encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(30, 10, str(row['customer_id']), 1, 0, 'C')
        pdf.cell(100, 10, name, 1, 0)
        pdf.cell(60, 10, f"{row['pending_amount']:.2f}", 1, 1, 'R')
        
    # Total Calculation - Adjusted to span correctly
    total_pending = df['pending_amount'].sum()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(130, 10, 'Total Pending Amount', 1, 0, 'R')
    pdf.cell(60, 10, f"{total_pending:.2f}", 1, 1, 'R')
    
    # Report Date
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(0, 10, f"Report generated on: {datetime.now().strftime('%d-%m-%Y')}", 0, 1, 'L')
    
    # Return PDF as bytes
    return pdf.output()

def generate_payment_history_pdf(df, customer_name, customer_id):
    """Generates a PDF report for a customer's payment history."""
    pdf = PDF()
    pdf.add_page()
    
    # Add a specific header for the payment history
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, f'Payment History for: {customer_name} (ID: {customer_id})', 0, 1, 'C')
    pdf.ln(10)

    # Table Header
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(95, 10, 'Payment Date', 1, 0, 'C')
    pdf.cell(95, 10, 'Payment Amount (Rs)', 1, 1, 'C')

    pdf.set_font('Helvetica', '', 11)
    # Table Body
    for index, row in df.iterrows():
        payment_date = datetime.strptime(row['payment_date'], '%Y-%m-%d').strftime('%d-%m-%Y')
        pdf.cell(95, 10, payment_date, 1, 0, 'C')
        pdf.cell(95, 10, f"{row['payment_amount']:.2f}", 1, 1, 'R')

    # Total Calculation
    total_paid = df['payment_amount'].sum()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(95, 10, 'Total Amount Paid', 1, 0, 'R')
    pdf.cell(95, 10, f"{total_paid:.2f}", 1, 1, 'R')

    # Report Date
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(0, 10, f"Report generated on: {datetime.now().strftime('%d-%m-%Y')}", 0, 1, 'L')
    
    return pdf.output()


# --- Database Setup ---
def init_db():
    """Initializes the SQLite database and creates/updates the tables."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    # Create customers table if it doesn't exist
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

    # Create payment_history table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS payment_history (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            payment_amount REAL NOT NULL,
            payment_date DATE NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
    ''')

    # --- Migration: Check if bill_date column exists and drop it safely ---
    try:
        c.execute("PRAGMA table_info(customers)")
        columns = [row[1] for row in c.fetchall()]
        if 'bill_date' in columns:
            # Use the safe method to drop a column in SQLite
            c.execute('CREATE TABLE customers_new AS SELECT customer_id, name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount FROM customers')
            c.execute('DROP TABLE customers')
            c.execute('ALTER TABLE customers_new RENAME TO customers')
            st.toast("Database schema updated: 'bill_date' column removed successfully.")
    except Exception:
        # This will prevent errors if the table is brand new or already migrated.
        pass

    conn.commit()
    conn.close()


# --- Database Operations ---
def add_customer(name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount):
    """Adds a new customer to the database."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
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

def get_payment_history_by_customer_id(customer_id):
    """Retrieves payment history for a specific customer, including their name."""
    conn = sqlite3.connect('isp_payments.db')
    query = f"""
        SELECT 
            ph.customer_id,
            c.name,
            ph.payment_amount,
            ph.payment_date
        FROM payment_history ph
        JOIN customers c ON ph.customer_id = c.customer_id
        WHERE ph.customer_id = {customer_id}
        ORDER BY ph.payment_date DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def update_customer(customer_id, name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount):
    """Updates an existing customer's details."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
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

def update_pending_amounts():
    """Checks for overdue renewals and updates pending amounts and renewal dates automatically."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    today = datetime.now().date()
    c.execute("SELECT customer_id, per_month_cost, internet_renewal_date, pending_amount FROM customers WHERE internet_renewal_date IS NOT NULL")
    customers_to_check = c.fetchall()

    for customer in customers_to_check:
        customer_id, per_month_cost, renewal_date_str, pending_amount = customer
        try:
            renewal_date = datetime.strptime(renewal_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            continue 

        if renewal_date < today:
            months_past = 0
            temp_renewal_date = renewal_date
            while temp_renewal_date < today:
                months_past += 1
                temp_renewal_date += timedelta(days=30)
            
            if months_past > 0:
                new_pending_amount = pending_amount + (per_month_cost * months_past)
                new_renewal_date = temp_renewal_date
                c.execute('''
                    UPDATE customers
                    SET pending_amount = ?, internet_renewal_date = ?
                    WHERE customer_id = ?
                ''', (new_pending_amount, new_renewal_date.strftime('%Y-%m-%d'), customer_id))
    conn.commit()
    conn.close()

def record_payment(customer_id, amount_paid):
    """Records a payment for a customer, updates their pending amount, and logs the transaction."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    try:
        c.execute("SELECT pending_amount, internet_renewal_date FROM customers WHERE customer_id = ?", (customer_id,))
        customer_data = c.fetchone()
        if customer_data:
            current_pending_amount, current_renewal_date_str = customer_data
            new_pending_amount = current_pending_amount - amount_paid
            try:
                current_renewal_date = datetime.strptime(current_renewal_date_str, '%Y-%m-%d').date()
                new_renewal_date = current_renewal_date + timedelta(days=30)
            except (ValueError, TypeError):
                new_renewal_date = datetime.now().date() + timedelta(days=30)
            c.execute('''
                UPDATE customers
                SET pending_amount = ?, internet_renewal_date = ?
                WHERE customer_id = ?
            ''', (new_pending_amount, new_renewal_date.strftime('%Y-%m-%d'), customer_id))
            c.execute('''
                INSERT INTO payment_history (customer_id, payment_amount, payment_date)
                VALUES (?, ?, ?)
            ''', (customer_id, amount_paid, datetime.now().date().strftime('%Y-%m-%d')))
            conn.commit()
            return True
        else:
            return False
    finally:
        conn.close()


# --- Helper function for date formatting ---
def format_df_dates(df, date_column='internet_renewal_date'):
    """Formats a DataFrame's date column to DD-MM-YYYY."""
    df_display = df.copy()
    if date_column in df_display.columns:
        df_display[date_column] = pd.to_datetime(df_display[date_column]).dt.strftime('%d-%m-%Y')
    return df_display

# --- Streamlit UI ---
st.set_page_config(page_title="ISP Payment Manager", layout="wide")

def main():
    """Main function to run the Streamlit app."""
    init_db()
    update_pending_amounts() # Automatically update amounts on page load
    st.title("ISP Customer Payment Manager")

    menu = ["View Customers", "Search Customer", "Add Customer", "Update/Delete Customer", "Record Payment", "Upcoming Renewals", "Payment History"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "View Customers":
        st.subheader("All Customers")
        customers_df = get_all_customers()
        if not customers_df.empty:
            customers_df_no_address = customers_df.drop(columns=['address'])
            display_df = format_df_dates(customers_df_no_address)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            if st.button("Generate PDF Report for Download"):
                with st.spinner('Generating PDF...'):
                    pdf_data = generate_pdf(customers_df[['customer_id', 'name', 'pending_amount']])
                    b64 = base64.b64encode(pdf_data).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="pending_amounts_{datetime.now().strftime("%Y%m%d")}.pdf">Click here to download your report</a>'
                    st.success("PDF Generated!")
                    st.markdown(href, unsafe_allow_html=True)
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
                today = pd.Timestamp.now().floor('D')
                next_10_days = today + timedelta(days=10)
                upcoming_renewals = customers_df[(customers_df['internet_renewal_date'] >= today) & (customers_df['internet_renewal_date'] <= next_10_days)].sort_values(by='internet_renewal_date')
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

    elif choice == "Payment History":
        st.subheader("Customer Payment History")
        customers_df = get_all_customers()
        if not customers_df.empty:
            customer_list = [f"{row['customer_id']} - {row['name']}" for index, row in customers_df.iterrows()]
            selected_customer_str = st.selectbox("Select a Customer to view their payment history", customer_list)
            if selected_customer_str:
                selected_customer_id = int(selected_customer_str.split(" - ")[0])
                customer_name = selected_customer_str.split(" - ")[1]
                history_df = get_payment_history_by_customer_id(selected_customer_id)
                if not history_df.empty:
                    st.write(f"#### Displaying history for {customer_name}")
                    display_history_df = history_df.copy()
                    display_history_df['payment_date'] = pd.to_datetime(display_history_df['payment_date']).dt.strftime('%d-%m-%Y')
                    st.dataframe(display_history_df[['customer_id', 'name', 'payment_amount', 'payment_date']], use_container_width=True, hide_index=True)
                    if st.button("Generate History PDF for Download"):
                        with st.spinner('Generating PDF...'):
                            pdf_data = generate_payment_history_pdf(history_df, customer_name, selected_customer_id)
                            b64 = base64.b64encode(pdf_data).decode()
                            href = f'<a href="data:application/pdf;base64,{b64}" download="payment_history_{selected_customer_id}_{datetime.now().strftime("%Y%m%d")}.pdf">Click here to download the history report</a>'
                            st.success("PDF Generated!")
                            st.markdown(href, unsafe_allow_html=True)
                else:
                    st.info(f"No payment history found for {customer_name}.")
        else:
            st.info("No customers in the database.")


if __name__ == '__main__':
    main()

