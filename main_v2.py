"""
Smart AI Recruiter - Main Entry Point (V2 with Folder Selection)
"""
import streamlit as st

# Set page config (must be first Streamlit command)
st.set_page_config(
    page_title="Smart AI Recruiter V2",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style sidebar navigation - rename "main" to "Smart AI Recruiter" with custom styling
st.markdown("""
<style>
/* Target the main page link in sidebar and change its text and styling */
section[data-testid="stSidebar"] nav ul:first-child li:first-child a,
section[data-testid="stSidebar"] nav a[href*="main"],
section[data-testid="stSidebar"] nav a[href="/"] {
    font-size: 1.3rem !important;
    font-weight: bold !important;
    color: #1f77b4 !important;
    padding: 0.5rem 0 !important;
}

/* Multiple approaches to hide and replace text */
section[data-testid="stSidebar"] nav ul:first-child li:first-child a span,
section[data-testid="stSidebar"] nav a[href*="main"] span,
section[data-testid="stSidebar"] nav a[href="/"] span {
    font-size: 1.3rem !important;
    font-weight: bold !important;
    color: #1f77b4 !important;
}

/* Hide original "main" text using multiple methods */
section[data-testid="stSidebar"] nav ul:first-child li:first-child a span:not([data-replaced]),
section[data-testid="stSidebar"] nav a[href*="main"] span:not([data-replaced]),
section[data-testid="stSidebar"] nav a[href="/"] span:not([data-replaced]) {
    position: relative !important;
}

/* Use ::before to add replacement text */
section[data-testid="stSidebar"] nav ul:first-child li:first-child a::before,
section[data-testid="stSidebar"] nav a[href*="main"]::before,
section[data-testid="stSidebar"] nav a[href="/"]::before {
    content: "Smart AI Recruiter V2" !important;
    font-size: 1.3rem !important;
    font-weight: bold !important;
    color: #1f77b4 !important;
    display: inline-block !important;
    position: absolute !important;
    left: 0 !important;
    background: white !important;
    padding-right: 5px !important;
}

/* Hide the original text by making it transparent and small */
section[data-testid="stSidebar"] nav ul:first-child li:first-child a {
    position: relative !important;
}

section[data-testid="stSidebar"] nav ul:first-child li:first-child a span {
    opacity: 0 !important;
    font-size: 0 !important;
    display: inline-block !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
}
</style>
""", unsafe_allow_html=True)

# Use components to inject JavaScript for sidebar text replacement
import streamlit.components.v1 as components

components.html("""
<script>
(function() {
    function updateSidebarText() {
        const sidebar = document.querySelector('section[data-testid="stSidebar"]');
        if (sidebar) {
            // Try multiple selectors to find the main link
            const allLinks = sidebar.querySelectorAll('nav a, nav li a, [data-baseweb="button"]');
            allLinks.forEach(function(link) {
                const href = link.getAttribute('href') || '';
                const text = link.textContent || '';
                
                // Check if this is the main page link
                if (href.includes('main') || href === '/' || text.trim().toLowerCase() === 'main') {
                    // Find all text nodes and spans
                    const spans = link.querySelectorAll('span');
                    spans.forEach(function(span) {
                        if (span.textContent.trim().toLowerCase() === 'main') {
                            span.textContent = 'Smart AI Recruiter V2';
                            span.style.fontSize = '1.3rem';
                            span.style.fontWeight = 'bold';
                            span.style.color = '#1f77b4';
                        }
                    });
                    
                    // Also try direct text content replacement
                    if (link.textContent.trim().toLowerCase() === 'main') {
                        link.innerHTML = '<span style="font-size: 1.3rem; font-weight: bold; color: #1f77b4;">Smart AI Recruiter V2</span>';
                    }
                }
            });
            
            // Also check for direct text nodes
            const walker = document.createTreeWalker(
                sidebar,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            
            let node;
            while (node = walker.nextNode()) {
                if (node.textContent.trim().toLowerCase() === 'main') {
                    node.textContent = 'Smart AI Recruiter V2';
                    // Try to style the parent
                    if (node.parentElement) {
                        node.parentElement.style.fontSize = '1.3rem';
                        node.parentElement.style.fontWeight = 'bold';
                        node.parentElement.style.color = '#1f77b4';
                    }
                }
            }
        }
    }
    
    // Run immediately
    updateSidebarText();
    
    // Run on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateSidebarText);
    } else {
        updateSidebarText();
    }
    
    // Use MutationObserver to catch dynamic updates
    const observer = new MutationObserver(function(mutations) {
        updateSidebarText();
    });
    
    // Observe the sidebar for changes
    const sidebar = document.querySelector('section[data-testid="stSidebar"]');
    if (sidebar) {
        observer.observe(sidebar, {
            childList: true,
            subtree: true,
            characterData: true
        });
    }
    
    // Also run after delays to catch dynamic content
    setTimeout(updateSidebarText, 100);
    setTimeout(updateSidebarText, 300);
    setTimeout(updateSidebarText, 500);
    setTimeout(updateSidebarText, 1000);
})();
</script>
""", height=0)

# Project Name in bigger font
st.markdown("""
<style>
.big-title {
    font-size: 3.5rem;
    font-weight: bold;
    text-align: center;
    color: #1f77b4;
    margin-bottom: 2rem;
}

.welcome-message {
    text-align: center;
    padding: 2rem;
    margin-top: 2rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    color: white;
}

.welcome-message h2 {
    color: white;
    font-size: 2rem;
    margin-bottom: 1rem;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
}

.welcome-message p {
    font-size: 1.2rem;
    line-height: 1.8;
    margin: 0;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.2);
}
</style>
<div class="big-title">Smart AI Recruiter V2</div>
""", unsafe_allow_html=True)

st.markdown("---")

# Fancy Welcome Message
st.markdown("""
<div class="welcome-message">
    <h2>🎉 Welcome to Smart AI Recruiter V2!</h2>
    <p>Transform your recruitment process with AI-powered resume screening.<br>
    <strong>NEW:</strong> Select any folder from your system as the base folder for candidate organization.<br>
    Navigate through our intuitive pages to discover powerful tools for talent acquisition.</p>
</div>
""", unsafe_allow_html=True)

