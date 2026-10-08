import streamlit as st
import pymongo

# Page Configuration
st.set_page_config(page_title="Chai FinLab Dashboard", layout="wide")
st.title("☕ Chai FinLab: Alpha Reports")
st.markdown("Automated fundamental analysis powered by the Chai Formula.")
st.divider()

# Initialize MongoDB Connection
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(st.secrets["MONGO_URI"])

try:
    client = init_connection()
    db = client.chai_finlab
    collection = db.alpha_reports
    reports = list(collection.find())

    if not reports:
        st.info("No reports found in the database. Run analyst.py to generate data.")
    else:
        # Display each report in an expandable card
        for report in reports:
            ticker = report.get("ticker", "Unknown Ticker")
            verdict = report.get("chai_formula_verdict", "No verdict available.")
            
            with st.expander(f"📊 {ticker} Analysis"):
                st.write(verdict)
                if "metrics" in report:
                    st.json(report["metrics"])
                    
except Exception as e:
    st.error(f"Database connection failed: {e}")