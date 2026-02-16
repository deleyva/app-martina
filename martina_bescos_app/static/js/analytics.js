const SESSION_COOKIE_NAME = 'analytics_session';
const TRACKING_ENDPOINT = '/analytics/track/';

// Function to generate a simple UUID (or use libraries like uuid)
function generateUUID() {
    // Generate random UUID
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Function to send tracking data
function sendTrackingData(eventType, data) {
    const sessionKey = localStorage.getItem(SESSION_COOKIE_NAME) || generateUUID();
    localStorage.setItem(SESSION_COOKIE_NAME, sessionKey);

    const trackingData = {
        session_key: sessionKey,
        event_type: eventType,
        url: window.location.href,
        title: document.title,
        timestamp: new Date().toISOString(),
        ...data
    };

    fetch(TRACKING_ENDPOINT, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') // Function to get CSRF token
        },
        body: JSON.stringify(trackingData)
    }).catch(error => console.error('Error sending tracking data:', error));
}

// Function to get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Track page view on load
window.addEventListener('load', () => {
    sendTrackingData('pageview', {});
});

// Track clicks
document.addEventListener('click', (event) => {
    const target = event.target;
    const targetElement = `${target.tagName.toLowerCase()}${target.id ? '#' + target.id : ''}${target.className ? '.' + target.className.replace(/\s+/g, '.') : ''}`;

    sendTrackingData('interaction', {
        target_element: targetElement,
        target_text: target.innerText ? target.innerText.substring(0, 100) : '',
        x: event.clientX,
        y: event.clientY
    });
});

// Track details toggle (Accordions)
document.addEventListener('toggle', (event) => {
    if (event.target.tagName.toLowerCase() === 'details') {
        const target = event.target;
        const isOpen = target.open;
        const summary = target.querySelector('summary');
        const title = summary ? summary.innerText.trim() : 'Unknown';

        sendTrackingData('accordion_toggle', {
            target_element: `details.${target.className.replace(/\s+/g, '.')}`,
            target_text: title,
            action: isOpen ? 'open' : 'close'
        });
    }
}, true); // Use capture to catch toggle events which don't bubble
