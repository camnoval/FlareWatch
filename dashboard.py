# dashboard.py - Streamlit Dashboard Optimized for Render
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import time
import os

# Configuration for Render deployment
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')

# Remove trailing slash if present
if API_BASE_URL.endswith('/'):
    API_BASE_URL = API_BASE_URL[:-1]

# Page config
st.set_page_config(
    page_title="MS Gait Pharmacist Dashboard", 
    layout="wide",
    page_icon="💊"
)

# Initialize session state for alerts and connection status
if 'last_alert_check' not in st.session_state:
    st.session_state.last_alert_check = datetime.now()
if 'recent_alerts' not in st.session_state:
    st.session_state.recent_alerts = []
if 'connection_status' not in st.session_state:
    st.session_state.connection_status = 'unknown'

# API functions with error handling
def test_api_connection():
    """Test connection to backend API"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            st.session_state.connection_status = 'connected'
            return data
        else:
            st.session_state.connection_status = 'error'
            return None
    except Exception as e:
        st.session_state.connection_status = 'failed'
        return None

@st.cache_data(ttl=60)  # Cache for 1 minute
def get_patients():
    """Get list of patients with recent activity"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/patients", timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        st.error(f"Failed to fetch patients: {str(e)}")
        return []

@st.cache_data(ttl=30)  # Cache for 30 seconds
def get_patient_data(patient_id, days=30):
    """Get patient gait data"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/patient/{patient_id}/data?days={days}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                # Convert timestamp strings back to datetime
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
            return pd.DataFrame()
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to fetch patient data: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_medication_history(patient_id):
    """Get medication change history"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/patient/{patient_id}/medication-history", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                if 'change_date' in df.columns:
                    df['change_date'] = pd.to_datetime(df['change_date'])
                return df
            return pd.DataFrame()
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to fetch medication history: {str(e)}")
        return pd.DataFrame()

def log_medication_change(patient_id, medication_name, old_dosage, new_dosage, reason, pharmacist_id):
    """Log a new medication change"""
    data = {
        'patient_id': patient_id,
        'change_date': datetime.now().isoformat(),
        'medication_name': medication_name,
        'old_dosage': old_dosage,
        'new_dosage': new_dosage,
        'reason': reason,
        'pharmacist_id': pharmacist_id
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/medication-change", json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Failed to log medication change: {str(e)}")
        return False

def update_patient_thresholds(patient_id, thresholds):
    """Update patient alert thresholds"""
    try:
        response = requests.post(f"{API_BASE_URL}/api/patient/{patient_id}/thresholds", json=thresholds, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Failed to update thresholds: {str(e)}")
        return False

# Dashboard UI
st.title("💊 Pharmacist Dashboard - Gait Monitoring")
st.caption(f"Real-time monitoring and medication adjustment tracking for MS/Parkinson's patients")

# Test API connection and show status
health_data = test_api_connection()

# Header with connection status and controls
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.subheader(f"API: {API_BASE_URL}")

with col2:
    if st.session_state.connection_status == 'connected':
        st.success("🟢 Connected")
        if health_data:
            st.caption(f"DB: {health_data.get('database', 'unknown')}")
    elif st.session_state.connection_status == 'error':
        st.error("🔴 API Error")
    else:
        st.warning("🟡 Connecting...")

with col3:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

# Show connection details if available
if health_data:
    with st.expander("System Status"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Active Patients", health_data.get('active_patients', 0))
        with col2:
            st.metric("Active Pharmacists", health_data.get('active_pharmacists', 0))
        with col3:
            st.metric("Database", health_data.get('database', 'unknown'))

# Patient selection
patients = get_patients()
if not patients:
    st.warning("No patients found. Ensure the backend is running and patients have sent data.")
    
    with st.expander("Troubleshooting"):
        st.write("**Common issues:**")
        st.write("1. Backend server not running")
        st.write("2. Database connection failed")
        st.write("3. No patient data has been sent yet")
        st.write(f"4. API URL incorrect: `{API_BASE_URL}`")
        
        if st.button("Test Connection"):
            health_data = test_api_connection()
            if health_data:
                st.success("✅ Connection successful!")
                st.json(health_data)
            else:
                st.error("❌ Connection failed")
    
    st.stop()

# Patient selection dropdown
patient_options = {}
for p in patients:
    last_update = p.get('last_update', 'Unknown')
    if isinstance(last_update, str) and last_update != 'Unknown':
        try:
            # Format timestamp for display
            dt = pd.to_datetime(last_update)
            formatted_time = dt.strftime('%m/%d %H:%M')
            patient_options[f"{p['patient_id']} (Last: {formatted_time})"] = p['patient_id']
        except:
            patient_options[f"{p['patient_id']} (Last: {last_update})"] = p['patient_id']
    else:
        patient_options[f"{p['patient_id']} (No recent data)"] = p['patient_id']

selected_patient_display = st.selectbox("Select Patient", list(patient_options.keys()))
selected_patient = patient_options[selected_patient_display]

# Get patient data
df = get_patient_data(selected_patient, days=30)
if df.empty:
    st.warning(f"No data found for patient {selected_patient}")
    st.info("This could mean:")
    st.write("- Patient hasn't sent data recently")
    st.write("- Database connection issues")
    st.write("- Patient ID doesn't exist")
    st.stop()

# Sort data by timestamp
df = df.sort_values('timestamp')

# Main dashboard tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Gait Analysis", "💊 Medication Tracking", "🔔 Alert Management", "📈 Correlation Analysis"])

with tab1:
    st.subheader(f"Gait Analysis - {selected_patient}")
    
    # Metrics overview
    col1, col2, col3, col4 = st.columns(4)
    
    latest_data = df.iloc[-1] if not df.empty else None
    
    with col1:
        if latest_data is not None and pd.notna(latest_data.get('walking_speed')):
            speed = latest_data['walking_speed']
            delta_color = "inverse" if speed < 0.8 else "normal"
            st.metric(
                "Walking Speed", 
                f"{speed:.2f} m/s",
                delta=f"Target: 0.8+ m/s",
                delta_color=delta_color
            )
        else:
            st.metric("Walking Speed", "No data")
    
    with col2:
        if latest_data is not None and pd.notna(latest_data.get('walking_asymmetry')):
            asymmetry = latest_data['walking_asymmetry']
            delta_color = "inverse" if asymmetry > 10 else "normal"
            st.metric(
                "Asymmetry", 
                f"{asymmetry:.1f}%",
                delta=f"Target: <10%",
                delta_color=delta_color
            )
        else:
            st.metric("Asymmetry", "No data")
    
    with col3:
        if latest_data is not None and pd.notna(latest_data.get('double_support_time')):
            support = latest_data['double_support_time']
            delta_color = "inverse" if support > 30 else "normal"
            st.metric(
                "Double Support", 
                f"{support:.1f}%",
                delta=f"Target: <30%",
                delta_color=delta_color
            )
        else:
            st.metric("Double Support", "No data")
            
    with col4:
        if latest_data is not None and pd.notna(latest_data.get('step_count')):
            st.metric("Step Count", f"{latest_data['step_count']:,}")
        else:
            st.metric("Step Count", "No data")
    
    # Time range selector
    col1, col2 = st.columns([3, 1])
    with col2:
        time_range = st.selectbox("Time Range", ["7 days", "14 days", "30 days"], index=2)
        days_map = {"7 days": 7, "14 days": 14, "30 days": 30}
        selected_days = days_map[time_range]
    
    # Filter data based on selection
    cutoff_date = datetime.now() - timedelta(days=selected_days)
    df_filtered = df[df['timestamp'] >= cutoff_date]
    
    if df_filtered.empty:
        st.warning(f"No data in the last {selected_days} days")
    else:
        # Time series plots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Walking Speed (m/s)', 'Gait Asymmetry (%)', 'Double Support Time (%)', 'Step Count'),
            vertical_spacing=0.1
        )
        
        # Walking Speed
        if 'walking_speed' in df_filtered.columns and not df_filtered['walking_speed'].isna().all():
            fig.add_trace(
                go.Scatter(x=df_filtered['timestamp'], y=df_filtered['walking_speed'], 
                          name='Walking Speed', line=dict(color='blue')),
                row=1, col=1
            )
            fig.add_hline(y=0.8, line_dash="dash", line_color="red", row=1, col=1)
        
        # Asymmetry 
        if 'walking_asymmetry' in df_filtered.columns and not df_filtered['walking_asymmetry'].isna().all():
            fig.add_trace(
                go.Scatter(x=df_filtered['timestamp'], y=df_filtered['walking_asymmetry'], 
                          name='Asymmetry', line=dict(color='orange')),
                row=1, col=2
            )
            fig.add_hline(y=10, line_dash="dash", line_color="red", row=1, col=2)
        
        # Double Support
        if 'double_support_time' in df_filtered.columns and not df_filtered['double_support_time'].isna().all():
            fig.add_trace(
                go.Scatter(x=df_filtered['timestamp'], y=df_filtered['double_support_time'], 
                          name='Double Support', line=dict(color='green')),
                row=2, col=1
            )
            fig.add_hline(y=30, line_dash="dash", line_color="red", row=2, col=1)
        
        # Step Count
        if 'step_count' in df_filtered.columns and not df_filtered['step_count'].isna().all():
            fig.add_trace(
                go.Scatter(x=df_filtered['timestamp'], y=df_filtered['step_count'], 
                          name='Step Count', line=dict(color='purple')),
                row=2, col=2
            )
        
        fig.update_layout(height=600, showlegend=False, title_text=f"Gait Metrics Over Time ({time_range})")
        st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        st.subheader("Recent Data")
        display_df = df_filtered.tail(10).copy()
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%m/%d %H:%M')
        
        # Select relevant columns for display
        display_cols = ['timestamp', 'walking_speed', 'walking_asymmetry', 'double_support_time', 'step_count']
        available_cols = [col for col in display_cols if col in display_df.columns]
        
        st.dataframe(
            display_df[available_cols].sort_values('timestamp', ascending=False),
            use_container_width=True,
            hide_index=True
        )

with tab2:
    st.subheader("💊 Medication Management")
    
    # Add new medication change
    with st.expander("📝 Log New Medication Change", expanded=False):
        with st.form("medication_form"):
            col1, col2 = st.columns(2)
            with col1:
                medication_name = st.text_input("Medication Name", placeholder="e.g., Levodopa")
                old_dosage = st.text_input("Previous Dosage", placeholder="e.g., 100mg 3x daily")
                pharmacist_id = st.text_input("Pharmacist ID", placeholder="e.g., PharmD_001")
            with col2:
                new_dosage = st.text_input("New Dosage", placeholder="e.g., 125mg 3x daily")
                reason = st.text_area("Reason for Change", placeholder="e.g., Patient reported increased tremor...")
            
            submitted = st.form_submit_button("Log Medication Change")
            
            if submitted:
                if medication_name and old_dosage and new_dosage and pharmacist_id:
                    success = log_medication_change(
                        selected_patient, medication_name, old_dosage, 
                        new_dosage, reason, pharmacist_id
                    )
                    if success:
                        st.success("✅ Medication change logged successfully!")
                        st.cache_data.clear()  # Clear cache to refresh data
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to log medication change")
                else:
                    st.error("Please fill in all required fields (Medication Name, Previous Dosage, New Dosage, Pharmacist ID)")
    
    # Display medication history
    med_history = get_medication_history(selected_patient)
    if not med_history.empty:
        st.subheader("📋 Medication History")
        
        # Format the data for display
        display_med = med_history.copy()
        display_med['change_date'] = display_med['change_date'].dt.strftime('%Y-%m-%d %H:%M')
        display_med = display_med.sort_values('change_date', ascending=False)
        
        st.dataframe(
            display_med[['change_date', 'medication_name', 'old_dosage', 'new_dosage', 'reason', 'pharmacist_id']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("📄 No medication changes recorded for this patient")

with tab3:
    st.subheader("🔔 Alert Configuration")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("Configure patient-specific alert thresholds:")
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            speed_threshold = st.number_input("Walking Speed Threshold (m/s)", value=0.8, min_value=0.1, max_value=2.0, step=0.1)
        with col_b:
            asymmetry_threshold = st.number_input("Asymmetry Threshold (%)", value=10.0, min_value=1.0, max_value=50.0, step=1.0)
        with col_c:
            support_threshold = st.number_input("Double Support Threshold (%)", value=30.0, min_value=10.0, max_value=60.0, step=1.0)
        
        if st.button("💾 Update Thresholds"):
            thresholds = {
                'walking_speed_threshold': speed_threshold,
                'asymmetry_threshold': asymmetry_threshold,
                'double_support_threshold': support_threshold
            }
            
            success = update_patient_thresholds(selected_patient, thresholds)
            if success:
                st.success("✅ Thresholds updated successfully!")
            else:
                st.error("❌ Failed to update thresholds")
    
    with col2:
        st.write("**Current Status:**")
        if latest_data is not None:
            # Check current values against thresholds
            alerts_active = []
            
            speed = latest_data.get('walking_speed')
            if speed and speed < speed_threshold:
                alerts_active.append("🔴 Speed Alert")
            
            asymmetry = latest_data.get('walking_asymmetry')  
            if asymmetry and asymmetry > asymmetry_threshold:
                alerts_active.append("🟠 Asymmetry Alert")
                
            support = latest_data.get('double_support_time')
            if support and support > support_threshold:
                alerts_active.append("🟠 Support Alert")
            
            if alerts_active:
                for alert in alerts_active:
                    st.warning(alert)
            else:
                st.success("✅ All metrics normal")
        else:
            st.info("No recent data to evaluate")
    
    # Recent alerts from data
    st.subheader("🚨 Recent Alert Activity")
    
    if not df.empty:
        # Check for alerts in recent data
        alert_data = df[
            (df.get('asymmetry_alert', False) == True) | 
            (df.get('double_support_alert', False) == True) |
            (df.get('walking_speed', 999) < speed_threshold)
        ].tail(10)
        
        if not alert_data.empty:
            alert_display = alert_data.copy()
            alert_display['timestamp'] = alert_display['timestamp'].dt.strftime('%m/%d %H:%M')
            
            cols_to_show = ['timestamp', 'walking_speed', 'walking_asymmetry', 'double_support_time']
            available_cols = [col for col in cols_to_show if col in alert_display.columns]
            
            st.dataframe(
                alert_display[available_cols],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("📋 No recent alerts for this patient")
    else:
        st.info("📋 No data available for alert analysis")

with tab4:
    st.subheader("📈 Medication Impact Analysis")
    
    # Get medication changes for correlation
    med_history = get_medication_history(selected_patient)
    
    if not med_history.empty and not df.empty:
        st.write("**Correlation between medication changes and gait metrics:**")
        
        # Create correlation plot
        fig = go.Figure()
        
        # Plot walking speed over time if available
        if 'walking_speed' in df.columns and not df['walking_speed'].isna().all():
            fig.add_trace(go.Scatter(
                x=df['timestamp'], 
                y=df['walking_speed'],
                mode='lines+markers',
                name='Walking Speed (m/s)',
                line=dict(color='blue'),
                yaxis='y1'
            ))
            
            # Add threshold line
            fig.add_hline(y=0.8, line_dash="dash", line_color="red", annotation_text="Speed Threshold")
        
        # Add vertical lines for medication changes
        for _, change in med_history.iterrows():
            change_date = change['change_date']
            hover_text = f"{change['medication_name']}<br>{change['old_dosage']} → {change['new_dosage']}"
            
            fig.add_vline(
                x=change_date,
                line_dash="dot",
                line_color="purple",
                annotation_text=change['medication_name'],
                annotation_position="top"
            )
        
        fig.update_layout(
            title="Walking Speed vs Medication Changes",
            xaxis_title="Date",
            yaxis_title="Walking Speed (m/s)",
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Before/After Analysis
        st.subheader("📊 Before/After Analysis")
        
        analysis_results = []
        
        for _, change in med_history.iterrows():
            change_date = change['change_date']
            
            # Get data 7 days before and after the change
            before_data = df[
                (df['timestamp'] <= change_date) & 
                (df['timestamp'] >= change_date - timedelta(days=7))
            ]
            after_data = df[
                (df['timestamp'] > change_date) & 
                (df['timestamp'] <= change_date + timedelta(days=7))
            ]
            
            if not before_data.empty and not after_data.empty and 'walking_speed' in df.columns:
                before_avg = before_data['walking_speed'].mean()
                after_avg = after_data['walking_speed'].mean()
                
                if pd.notna(before_avg) and pd.notna(after_avg):
                    change_pct = ((after_avg - before_avg) / before_avg) * 100 if before_avg != 0 else 0
                    
                    analysis_results.append({
                        'Date': change_date.strftime('%Y-%m-%d'),
                        'Medication': change['medication_name'],
                        'Change': f"{change['old_dosage']} → {change['new_dosage']}",
                        'Speed Before': f"{before_avg:.2f} m/s",
                        'Speed After': f"{after_avg:.2f} m/s",
                        'Change %': f"{change_pct:+.1f}%",
                        'Trend': '📈 Improved' if change_pct > 5 else '📉 Declined' if change_pct < -5 else '➡️ Stable'
                    })
        
        if analysis_results:
            analysis_df = pd.DataFrame(analysis_results)
            st.dataframe(analysis_df, use_container_width=True, hide_index=True)
        else:
            st.info("📋 Insufficient data for before/after analysis")
            
        # Recommendations
        if analysis_results:
            st.subheader("💡 Insights")
            
            improved_changes = [r for r in analysis_results if '📈' in r['Trend']]
            declined_changes = [r for r in analysis_results if '📉' in r['Trend']]
            
            if improved_changes:
                st.success(f"✅ {len(improved_changes)} medication changes showed improvement")
                
            if declined_changes:
                st.warning(f"⚠️ {len(declined_changes)} medication changes preceded decline")
                st.write("Consider reviewing these adjustments:")
                for change in declined_changes:
                    st.write(f"- {change['Medication']} on {change['Date']}: {change['Change %']} change")
    
    else:
        st.info("📋 Need both gait data and medication history for correlation analysis")
        
        if med_history.empty:
            st.write("• No medication changes recorded")
        if df.empty:
            st.write("• No gait data available")

# Auto-refresh indicator
st.sidebar.markdown("---")
st.sidebar.markdown("**🔄 Auto-refresh**")
st.sidebar.caption("Data refreshes automatically based on cache settings")
st.sidebar.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

# Add a simple auto-refresh mechanism
if st.sidebar.button("🔄 Force Refresh All Data"):
    st.cache_data.clear()
    st.session_state.connection_status = 'unknown'
    st.rerun()
