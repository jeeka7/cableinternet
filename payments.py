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
    # Use parameters to prevent SQL injection
    customer_df = pd.read_sql_query("SELECT * FROM customers WHERE customer_id = ?", conn, params=(customer_id,))
    conn.close()
    return customer_df.iloc[0] if not customer_df.empty else None

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
        WHERE ph.customer_id = ?
        ORDER BY ph.payment_date DESC
    """
    df = pd.read_sql_query(query, conn, params=(customer_id,))
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
    c.execute("DELETE FROM payment_history WHERE customer_id = ?", (customer_id,)) # Also delete payment history
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
                # A more robust way to increment months
                if temp_renewal_date.month == 12:
                    temp_renewal_date = temp_renewal_date.replace(year=temp_renewal_date.year + 1, month=1)
                else:
                    temp_renewal_date = temp_renewal_date.replace(month=temp_renewal_date.month + 1)

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

def record_payment(customer_id, amount_paid, payment_date):
    """Records a payment for a customer, updates their pending amount, and logs the transaction."""
    conn = sqlite3.connect('isp_payments.db')
    c = conn.cursor()
    try:
        c.execute("SELECT pending_amount FROM customers WHERE customer_id = ?", (customer_id,))
        customer_data = c.fetchone()
        if customer_data:
            current_pending_amount = customer_data[0]
            new_pending_amount = current_pending_amount - amount_paid
            
            c.execute('''
                UPDATE customers
                SET pending_amount = ?
                WHERE customer_id = ?
            ''', (new_pending_amount, customer_id))
            
            c.execute('''
                INSERT INTO payment_history (customer_id, payment_amount, payment_date)
                VALUES (?, ?, ?)
            ''', (customer_id, amount_paid, payment_date.strftime('%Y-%m-%d')))
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
    if date_column in df_display.columns and not df_display.empty:
        df_display[date_column] = pd.to_datetime(df_display[date_column]).dt.strftime('%d-%m-%Y')
    return df_display

# --- Login and UI ---
st.set_page_config(page_title="ISP Payment Manager", layout="wide")

def login_page():
    st.header("Login")
    login_as = st.radio("Login as:", ("Admin", "Customer"))

    if login_as == "Admin":
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            # Check password against Streamlit secrets
            if password == st.secrets.get("ADMIN_PASSWORD"):
                st.session_state.logged_in = True
                st.session_state.role = "Admin"
                st.success("Logged in successfully as Admin!")
                st.rerun()
            else:
                st.error("Incorrect password")
    
    elif login_as == "Customer":
        customer_id = st.number_input("Enter your Customer ID", min_value=1, step=1)
        if st.button("Login"):
            customer = get_customer_by_id(customer_id)
            if customer is not None:
                st.session_state.logged_in = True
                st.session_state.role = "Customer"
                st.session_state.customer_id = customer_id
                st.session_state.customer_name = customer['name']
                st.success(f"Logged in successfully as {st.session_state.customer_name}!")
                st.rerun()
            else:
                st.error("Customer ID not found.")

def main():
    """Main function to run the Streamlit app."""
    init_db()

    # Initialize session state variables
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'history_customer_id' not in st.session_state:
        st.session_state.history_customer_id = None
    if 'edit_customer_id' not in st.session_state:
        st.session_state.edit_customer_id = None
    if 'record_payment_customer_id' not in st.session_state:
        st.session_state.record_payment_customer_id = None


    if not st.session_state.logged_in:
        login_page()
        return

    # --- Main App for Logged-in Users ---
    
    st.sidebar.title(f"Welcome, {st.session_state.get('customer_name', 'Admin')}!")
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.title("ISP Customer Payment Manager")
    
    # --- Role-Based Menu ---
    if st.session_state.role == "Admin":
        update_pending_amounts() # Run auto-update only for Admin
        menu = ["View Customers", "Search Customer", "Add Customer", "Update/Delete Customer", "Record Payment", "Upcoming Renewals", "Payment History"]
        choice = st.sidebar.selectbox("Menu", menu)
        
        # Clear search states if we navigate away from the page
        if choice != "Payment History" and st.session_state.get('history_customer_id'):
            st.session_state.history_customer_id = None
        if choice != "Update/Delete Customer" and st.session_state.get('edit_customer_id'):
            st.session_state.edit_customer_id = None
        if choice != "Record Payment" and st.session_state.get('record_payment_customer_id'):
            st.session_state.record_payment_customer_id = None
    else: # Customer View
        menu = ["My Details", "My Payment History"]
        choice = st.sidebar.selectbox("Menu", menu)

    # --- Admin Pages ---
    if st.session_state.role == "Admin":
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
                if submitted and name:
                    add_customer(name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount)
                    st.success(f"Customer '{name}' added successfully!")
                elif submitted:
                    st.warning("Customer name is required.")

        elif choice == "Update/Delete Customer":
            st.subheader("Update or Delete Customer Information")
            
            customer_id_input = st.number_input("Enter Customer ID to Update or Delete", min_value=1, step=1)

            if st.button("Find Customer"):
                customer_data = get_customer_by_id(customer_id_input)
                if customer_data is not None:
                    st.session_state.edit_customer_id = customer_id_input
                else:
                    st.warning(f"No customer found with ID: {customer_id_input}")
                    st.session_state.edit_customer_id = None
            
            if st.session_state.get('edit_customer_id'):
                selected_customer_id = st.session_state.edit_customer_id
                customer_data = get_customer_by_id(selected_customer_id)
                
                if customer_data is not None:
                    with st.form("update_customer_form"):
                        st.write(f"**Editing Customer ID:** {customer_data['customer_id']}")
                        name = st.text_input("Name", value=customer_data['name'])
                        mobile = st.text_input("Mobile Number", value=customer_data['mobile'])
                        address = st.text_area("Address", value=customer_data['address'])
                        plan_details = st.text_input("Plan Details", value=customer_data['plan_details'])
                        per_month_cost = st.number_input("Per Month Cost (₹)", min_value=0.0, value=float(customer_data['per_month_cost']))
                        renewal_date_val = datetime.strptime(customer_data['internet_renewal_date'], '%Y-%m-%d').date() if customer_data['internet_renewal_date'] else datetime.now().date()
                        internet_renewal_date = st.date_input("Internet Renewal Date", value=renewal_date_val)
                        pending_amount = st.number_input("Pending Amount (₹)", min_value=0.0, value=float(customer_data['pending_amount']))
                        
                        col1, col2 = st.columns(2)
                        if col1.form_submit_button("Update Customer"):
                            update_customer(selected_customer_id, name, mobile, address, plan_details, per_month_cost, internet_renewal_date, pending_amount)
                            st.success(f"Customer ID {selected_customer_id} updated successfully!")
                            st.session_state.edit_customer_id = None # Clear state
                            st.rerun()
                        if col2.form_submit_button("Delete Customer"):
                            delete_customer(selected_customer_id)
                            st.warning(f"Customer ID {selected_customer_id} has been deleted.")
                            st.session_state.edit_customer_id = None # Clear state
                            st.rerun()


        elif choice == "Record Payment":
            st.subheader("Record a Customer Payment")
            
            customer_id_input = st.number_input("Enter Customer ID to Record Payment for", min_value=1, step=1)

            if st.button("Find Customer for Payment"):
                customer_data = get_customer_by_id(customer_id_input)
                if customer_data is not None:
                    st.session_state.record_payment_customer_id = customer_id_input
                else:
                    st.warning(f"No customer found with ID: {customer_id_input}")
                    st.session_state.record_payment_customer_id = None
            
            if st.session_state.get('record_payment_customer_id'):
                selected_customer_id = st.session_state.record_payment_customer_id
                customer_data = get_customer_by_id(selected_customer_id)

                if customer_data is not None:
                    st.write(f"**Recording payment for:** {customer_data['name']} (ID: {selected_customer_id})")
                    st.write(f"**Current Pending Amount:** ₹{customer_data['pending_amount']:.2f}")

                    with st.form("payment_form", clear_on_submit=True):
                        amount_paid = st.number_input("Amount Paid (₹)", min_value=0.01, step=50.0)
                        payment_date = st.date_input("Payment Date", value=datetime.now().date())
                        if st.form_submit_button("Record Payment"):
                            if record_payment(selected_customer_id, amount_paid, payment_date):
                                st.success(f"Payment of ₹{amount_paid} recorded for Customer ID {selected_customer_id}.")
                                st.session_state.record_payment_customer_id = None # Clear state after recording
                            else:
                                st.error("Failed to record payment.")
        
        elif choice == "Upcoming Renewals":
            st.subheader("Upcoming Renewals")
            customers_df = get_all_customers()
            if not customers_df.empty:
                customers_df['internet_renewal_date'] = pd.to_datetime(customers_df['internet_renewal_date'], errors='coerce')
                customers_df.dropna(subset=['internet_renewal_date'], inplace=True) # Drop rows where date conversion failed
                today = pd.Timestamp.now().floor('D')
                next_10_days = today + timedelta(days=10)

                st.write("Renewals in the next 10 days:")
                upcoming = customers_df[(customers_df['internet_renewal_date'] >= today) & (customers_df['internet_renewal_date'] <= next_10_days)].sort_values(by='internet_renewal_date')
                if not upcoming.empty:
                    st.dataframe(format_df_dates(upcoming), use_container_width=True, hide_index=True)
                else:
                    st.info("No upcoming renewals in the next 10 days.")
                
                st.write("Past Due Renewals:")
                past_due = customers_df[customers_df['internet_renewal_date'] < today].sort_values(by='internet_renewal_date')
                if not past_due.empty:
                    st.dataframe(format_df_dates(past_due), use_container_width=True, hide_index=True)
                else:
                    st.info("No customers with past due renewals.")

        elif choice == "Payment History":
            st.subheader("View Customer Payment History")
            
            customer_id_input = st.number_input("Enter Customer ID to view payment history", min_value=1, step=1)

            if st.button("View History"):
                customer_data = get_customer_by_id(customer_id_input)
                if customer_data is not None:
                    # Store the valid ID in session state, which triggers a rerun
                    st.session_state.history_customer_id = customer_id_input
                else:
                    # If ID is invalid, show a warning and clear the session state
                    st.warning(f"No customer found with ID: {customer_id_input}")
                    st.session_state.history_customer_id = None
            
            # This block now runs if a VALID customer ID has been found and stored in the session state
            if st.session_state.get('history_customer_id'):
                customer_id_to_view = st.session_state.history_customer_id
                customer_data = get_customer_by_id(customer_id_to_view) # Fetch data again
                
                if customer_data is not None:
                    customer_name = customer_data['name']
                    history_df = get_payment_history_by_customer_id(customer_id_to_view)

                    if not history_df.empty:
                        st.write(f"#### History for {customer_name} (ID: {customer_id_to_view})")
                        display_df = history_df.copy()
                        display_df['payment_date'] = pd.to_datetime(display_df['payment_date']).dt.strftime('%d-%m-%Y')
                        st.dataframe(display_df.drop(columns=['customer_id', 'name']), use_container_width=True, hide_index=True)
                        
                        if st.button("Generate History PDF"):
                            pdf_data = generate_payment_history_pdf(history_df, customer_name, customer_id_to_view)
                            b64 = base64.b64encode(pdf_data).decode()
                            href = f'<a href="data:application/pdf;base64,{b64}" download="history_{customer_id_to_view}.pdf">Download PDF</a>'
                            st.markdown(href, unsafe_allow_html=True)
                    else:
                        st.info(f"No payment history for {customer_name}.")


    # --- Customer Pages ---
    elif st.session_state.role == "Customer":
        customer_id = st.session_state.customer_id
        
        if choice == "My Details":
            st.subheader("My Account Details")
            customer_data = get_customer_by_id(customer_id)
            if customer_data is not None:
                customer_df = pd.DataFrame(customer_data).transpose()
                customer_df.columns = customer_data.index
                # Drop sensitive columns for customer view
                customer_display_df = customer_df.drop(columns=['mobile', 'address'])
                st.dataframe(format_df_dates(customer_display_df), use_container_width=True, hide_index=True)
            else:
                st.error("Could not retrieve your details.")

        elif choice == "My Payment History":
            st.subheader("My Payment History")
            history_df = get_payment_history_by_customer_id(customer_id)
            if not history_df.empty:
                display_df = history_df.copy()
                display_df['payment_date'] = pd.to_datetime(display_df['payment_date']).dt.strftime('%d-%m-%Y')
                st.dataframe(display_df.drop(columns=['customer_id', 'name']), use_container_width=True, hide_index=True)
                if st.button("Generate History PDF for Download"):
                    pdf_data = generate_payment_history_pdf(history_df, st.session_state.customer_name, customer_id)
                    b64 = base64.b64encode(pdf_data).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="my_payment_history.pdf">Click here to download</a>'
                    st.markdown(href, unsafe_allow_html=True)
            else:
                st.info("You have no payment history.")


if __name__ == '__main__':
    main()

