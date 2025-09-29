// ChordSheetJS integration for Music Cards
import ChordSheetJS from 'chordsheetjs';

// Make ChordSheetJS available globally
window.ChordSheetJS = ChordSheetJS;

// Convert Ultimate Guitar format to ChordPro format
function convertToChordPro(ultimateGuitarText) {
    try {
        console.log('Converting Ultimate Guitar to ChordPro:', ultimateGuitarText.substring(0, 50) + '...');
        
        // Parse with UltimateGuitarParser
        const parser = new ChordSheetJS.UltimateGuitarParser();
        const song = parser.parse(ultimateGuitarText);
        
        // Convert to ChordPro format
        const chordProFormatter = new ChordSheetJS.ChordProFormatter();
        const chordProText = chordProFormatter.format(song);
        
        console.log('Successfully converted to ChordPro');
        return chordProText;
        
    } catch (error) {
        console.error('Conversion to ChordPro failed:', error);
        console.log('Trying ChordsOverWordsParser for conversion...');
        
        // Fallback to ChordsOverWordsParser
        try {
            const parser2 = new ChordSheetJS.ChordsOverWordsParser();
            const song2 = parser2.parse(ultimateGuitarText);
            const chordProFormatter2 = new ChordSheetJS.ChordProFormatter();
            const chordProText2 = chordProFormatter2.format(song2);
            
            console.log('Successfully converted with ChordsOverWordsParser');
            return chordProText2;
        } catch (error2) {
            console.error('ChordPro conversion also failed:', error2);
            // Return original text if conversion fails
            return ultimateGuitarText;
        }
    }
}

// ChordSheetJS Parser for displaying chord sheets (Ultimate Guitar format)
function parseUltimateGuitarChords(chordSheetText) {
    try {
        console.log('Parsing Ultimate Guitar format:', chordSheetText.substring(0, 50) + '...');
        
        // Parse as Ultimate Guitar format
        const parser = new ChordSheetJS.UltimateGuitarParser();
        const song = parser.parse(chordSheetText);
        
        // Use HtmlTableFormatter for chord alignment
        const formatter = new ChordSheetJS.HtmlTableFormatter();
        const result = formatter.format(song);
        
        console.log('Successfully parsed Ultimate Guitar format');
        return result;
        
    } catch (error) {
        console.error('Ultimate Guitar parsing failed:', error);
        console.log('Trying ChordsOverWordsParser...');
        
        // Fallback: try ChordsOverWordsParser
        try {
            const parser2 = new ChordSheetJS.ChordsOverWordsParser();
            const song2 = parser2.parse(chordSheetText);
            const formatter2 = new ChordSheetJS.HtmlTableFormatter();
            const result2 = formatter2.format(song2);
            
            console.log('Successfully parsed with ChordsOverWordsParser');
            return result2;
        } catch (error2) {
            console.error('ChordsOverWordsParser also failed:', error2);
            console.log('Using fallback display');
            // Final fallback to simple display
            return `<pre class="chord-sheet-fallback">${chordSheetText}</pre>`;
        }
    }
}


// ChordPro initialization with ChordSheetJS
function initializeChordPro() {
    console.log('Initializing ChordPro...');
    const containers = document.querySelectorAll('.chordpro-container');
    console.log('Found', containers.length, 'ChordPro containers');
    
    containers.forEach(function(container, index) {
        const chordProContent = container.getAttribute('data-chordpro-content');
        console.log(`Container ${index + 1}:`, chordProContent ? chordProContent.substring(0, 50) + '...' : 'No content');
        
        if (chordProContent) {
            try {
                // Use ChordSheetJS for Ultimate Guitar format
                const parsedHtml = parseUltimateGuitarChords(chordProContent);
                container.innerHTML = parsedHtml;
                
                // Add styling classes to the generated content
                container.classList.add('chord-sheet-rendered');
                console.log(`Successfully parsed container ${index + 1}`);
            } catch (error) {
                console.error('Error parsing ChordPro:', error);
                // Fallback to simple display
                container.innerHTML = `<pre class="chord-sheet-fallback">${chordProContent}</pre>`;
            }
        }
    });
}

// Manual conversion function for buttons
function manualConvertToChordPro(textareaId) {
    const textarea = document.getElementById(textareaId);
    if (!textarea) {
        console.error('Textarea not found:', textareaId);
        return;
    }
    
    const content = textarea.value.trim();
    if (!content) {
        alert('No hay contenido para convertir');
        return;
    }
    
    if (isUltimateGuitarFormat(content)) {
        const chordProContent = convertToChordPro(content);
        textarea.value = chordProContent;
        
        // Trigger input event for frameworks that listen to it
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        
        alert('Contenido convertido a formato ChordPro');
        console.log('Manual conversion completed');
    } else {
        alert('El contenido no parece estar en formato Ultimate Guitar');
    }
}

// Export functions to global scope
window.parseUltimateGuitarChords = parseUltimateGuitarChords;
window.convertToChordPro = convertToChordPro;
window.manualConvertToChordPro = manualConvertToChordPro;
window.initializeChordPro = initializeChordPro;

// Handle paste events to preserve spacing
function handlePasteInTextarea(event) {
    // Get the pasted data
    const paste = (event.clipboardData || window.clipboardData).getData('text');
    
    // Prevent the default paste behavior
    event.preventDefault();
    
    // Insert the text preserving spaces
    const textarea = event.target;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    
    // Replace the selected text with the pasted content
    textarea.value = textarea.value.substring(0, start) + paste + textarea.value.substring(end);
    
    // Set the cursor position after the pasted content
    textarea.selectionStart = textarea.selectionEnd = start + paste.length;
    
    // Trigger input event for frameworks that listen to it
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    
    console.log('Paste intercepted and preserved spacing');
}

// HTMX-based conversion - no longer need form interception
// Conversion is now handled by HTMX buttons that call the server endpoint

// Detect if content is in Ultimate Guitar format
function isUltimateGuitarFormat(content) {
    // Check for Ultimate Guitar patterns:
    // 1. Section headers like [Verse 1], [Chorus]
    // 2. Chord lines followed by lyric lines
    // 3. Multiple spaces between chords
    
    const lines = content.split('\n');
    let hasUGSections = false;
    let hasChordLyricPairs = false;
    
    // Check for UG section headers
    hasUGSections = lines.some(line => /^\[.*\]$/.test(line.trim()));
    
    // Check for chord-lyric pairs
    for (let i = 0; i < lines.length - 1; i++) {
        const currentLine = lines[i];
        const nextLine = lines[i + 1];
        
        // Check if current line looks like chords and next line has lyrics
        const chordPattern = /^[A-G][#b]?[m]?[0-9]*[\/A-G#b]*(\s+[A-G][#b]?[m]?[0-9]*[\/A-G#b]*)*\s*$/;
        const isChordLine = chordPattern.test(currentLine.trim());
        const hasLyrics = nextLine && /[a-zA-Z]/.test(nextLine.trim());
        
        if (isChordLine && hasLyrics) {
            hasChordLyricPairs = true;
            break;
        }
    }
    
    // It's likely Ultimate Guitar format if it has UG sections OR chord-lyric pairs
    return hasUGSections || hasChordLyricPairs;
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        initializeChordPro();
        setupTextareaHandlers();
    }, 100);
});

// Re-initialize after HTMX swaps
document.addEventListener('htmx:afterSwap', function() {
    setTimeout(function() {
        initializeChordPro();
        setupTextareaHandlers();
    }, 100);
});

// Setup textarea paste handlers and HTMX conversion buttons
function setupTextareaHandlers() {
    const textareas = document.querySelectorAll('textarea');
    console.log('Setting up paste handlers for', textareas.length, 'textareas');
    
    textareas.forEach(textarea => {
        // Remove existing listener if any
        textarea.removeEventListener('paste', handlePasteInTextarea);
        // Add new listener
        textarea.addEventListener('paste', handlePasteInTextarea);
        console.log('Added paste handler to textarea:', textarea.name || textarea.id || 'unnamed');
    });
    
    // Setup HTMX conversion buttons
    const convertButtons = document.querySelectorAll('.convert-chordpro-btn');
    console.log('Setting up HTMX conversion for', convertButtons.length, 'buttons');
    
    convertButtons.forEach(button => {
        button.addEventListener('click', function() {
            const textareaIndex = this.getAttribute('data-textarea-index');
            const textarea = document.querySelector(`textarea[name="text_content_${textareaIndex}"]`);
            
            if (textarea) {
                // Make HTMX request
                htmx.ajax('POST', '/music-cards/convert-to-chordpro/', {
                    values: {
                        content: textarea.value,
                        textarea_id: `text_content_${textareaIndex}`,
                        textarea_name: `text_content_${textareaIndex}`
                    },
                    target: textarea.parentElement,
                    swap: 'outerHTML'
                });
            }
        });
    });
}

console.log('ChordSheetJS module loaded successfully');
