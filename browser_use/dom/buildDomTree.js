(
    doHighlightElements = true
) => {
    let highlightIndex = 0; // Reset highlight index

    function highlightElement(element, index, parentIframe = null) {
        // Create or get highlight container
        let container = document.getElementById('playwright-highlight-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'playwright-highlight-container';
            container.style.position = 'fixed';
            container.style.pointerEvents = 'none';
            container.style.top = '0';
            container.style.left = '0';
            container.style.width = '100%';
            container.style.height = '100%';
            container.style.zIndex = '2147483647'; // Maximum z-index value
            document.documentElement.appendChild(container);
        }

        // Generate a color based on the index
        const colors = [
            '#FF0000', '#00FF00', '#0000FF', '#FFA500', 
            '#800080', '#008080', '#FF69B4', '#4B0082',
            '#FF4500', '#2E8B57', '#DC143C', '#4682B4'
        ];
        const colorIndex = index % colors.length;
        const baseColor = colors[colorIndex];
        const backgroundColor = `${baseColor}1A`; // 10% opacity version of the color

        // Create highlight overlay
        const overlay = document.createElement('div');
        overlay.style.position = 'absolute';
        overlay.style.border = `2px solid ${baseColor}`;
        overlay.style.backgroundColor = backgroundColor;
        overlay.style.pointerEvents = 'none';
        overlay.style.boxSizing = 'border-box';

        // Position overlay based on element
        const rect = element.getBoundingClientRect();
        let top = rect.top;
        let left = rect.left;

        // Adjust position if element is inside an iframe
        if (parentIframe) {
            const iframeRect = parentIframe.getBoundingClientRect();
            top += iframeRect.top;
            left += iframeRect.left;
        }

        overlay.style.top = `${top}px`;
        overlay.style.left = `${left}px`;
        overlay.style.width = `${rect.width}px`;
        overlay.style.height = `${rect.height}px`;

        // Create label
        const label = document.createElement('div');
        label.className = 'playwright-highlight-label';
        label.style.position = 'absolute';
        label.style.background = baseColor;
        label.style.color = 'white';
        label.style.padding = '1px 4px';
        label.style.borderRadius = '4px';
        label.style.fontSize = `${Math.min(12, Math.max(8, rect.height / 2))}px`; // Responsive font size
        label.textContent = index;

        // Calculate label position
        const labelWidth = 20; // Approximate width
        const labelHeight = 16; // Approximate height
        
        // Default position (top-right corner inside the box)
        let labelTop = top + 2;
        let labelLeft = left + rect.width - labelWidth - 2;

        // Adjust if box is too small
        if (rect.width < labelWidth + 4 || rect.height < labelHeight + 4) {
            // Position outside the box if it's too small
            labelTop = top - labelHeight - 2;
            labelLeft = left + rect.width - labelWidth;
        }

        // Ensure label stays within viewport
        if (labelTop < 0) labelTop = top + 2;
        if (labelLeft < 0) labelLeft = left + 2;
        if (labelLeft + labelWidth > window.innerWidth) {
            labelLeft = left + rect.width - labelWidth - 2;
        }

        label.style.top = `${labelTop}px`;
        label.style.left = `${labelLeft}px`;

        // Add to container
        container.appendChild(overlay);
        container.appendChild(label);

        // Store reference for cleanup
        element.setAttribute('browser-user-highlight-id', `playwright-highlight-${index}`);

        return index + 1;
    }


    // Helper function to generate XPath as a tree
    function getXPathTree(element, stopAtBoundary = true) {
        const segments = [];
        let currentElement = element;

        while (currentElement && currentElement.nodeType === Node.ELEMENT_NODE) {
            // Stop if we hit a shadow root or iframe
            if (stopAtBoundary && (currentElement.parentNode instanceof ShadowRoot || currentElement.parentNode instanceof HTMLIFrameElement)) {
                break;
            }

            let index = 0;
            let sibling = currentElement.previousSibling;
            while (sibling) {
                if (sibling.nodeType === Node.ELEMENT_NODE &&
                    sibling.nodeName === currentElement.nodeName) {
                    index++;
                }
                sibling = sibling.previousSibling;
            }

            const tagName = currentElement.nodeName.toLowerCase();
            const xpathIndex = index > 0 ? `[${index + 1}]` : '';
            segments.unshift(`${tagName}${xpathIndex}`);

            currentElement = currentElement.parentNode;
        }

        return segments.join('/');
    }

    // Helper function to check if element is accepted
    function isElementAccepted(element) {
        const leafElementDenyList = new Set(['svg', 'script', 'style', 'link', 'meta']);
        return !leafElementDenyList.has(element.tagName.toLowerCase());
    }

    // Helper function to check if element is interactive
    function isInteractiveElement(element) {
        // Base interactive elements and roles
        const interactiveElements = new Set([
            'a', 'button', 'details', 'embed', 'input', 'label',
            'menu', 'menuitem', 'object', 'select', 'textarea', 'summary'
        ]);

        const interactiveRoles = new Set([
            'button', 'menu', 'menuitem', 'link', 'checkbox', 'radio',
            'slider', 'tab', 'tabpanel', 'textbox', 'combobox', 'grid',
            'listbox', 'option', 'progressbar', 'scrollbar', 'searchbox',
            'switch', 'tree', 'treeitem', 'spinbutton', 'tooltip', 'a-button-inner', 'a-dropdown-button', 'click',
            'menuitemcheckbox', 'menuitemradio', 'a-button-text', 'button-text', 'button-icon', 'button-icon-only', 'button-text-icon-only', 'dropdown', 'combobox' 
        ]);

        const tagName = element.tagName.toLowerCase();
        const role = element.getAttribute('role');
        const ariaRole = element.getAttribute('aria-role');
        const tabIndex = element.getAttribute('tabindex');

        // Basic role/attribute checks
        const hasInteractiveRole = interactiveElements.has(tagName) ||
            interactiveRoles.has(role) ||
            interactiveRoles.has(ariaRole) ||
            (tabIndex !== null && tabIndex !== '-1') ||
            element.getAttribute('data-action') === 'a-dropdown-select' ||
            element.getAttribute('data-action') === 'a-dropdown-button';

        if (hasInteractiveRole) return true;

        // Get computed style
        const style = window.getComputedStyle(element);

        // Check if element has click-like styling
        // const hasClickStyling = style.cursor === 'pointer' ||
        //     element.style.cursor === 'pointer' ||
        //     style.pointerEvents !== 'none';

        // Check for event listeners
        const hasClickHandler = element.onclick !== null ||
            element.getAttribute('onclick') !== null ||
            element.hasAttribute('ng-click') ||
            element.hasAttribute('@click') ||
            element.hasAttribute('v-on:click');

        // Helper function to safely get event listeners
        function getEventListeners(el) {
            try {
                // Try to get listeners using Chrome DevTools API
                return window.getEventListeners?.(el) || {};
            } catch (e) {
                // Fallback: check for common event properties
                const listeners = {};

                // List of common event types to check
                const eventTypes = [
                    'click', 'mousedown', 'mouseup',
                    'touchstart', 'touchend',
                    'keydown', 'keyup', 'focus', 'blur'
                ];

                for (const type of eventTypes) {
                    const handler = el[`on${type}`];
                    if (handler) {
                        listeners[type] = [{
                            listener: handler,
                            useCapture: false
                        }];
                    }
                }

                return listeners;
            }
        }

        // Check for click-related events on the element itself
        const listeners = getEventListeners(element);
        const hasClickListeners = listeners && (
            listeners.click?.length > 0 ||
            listeners.mousedown?.length > 0 ||
            listeners.mouseup?.length > 0 ||
            listeners.touchstart?.length > 0 ||
            listeners.touchend?.length > 0
        );

        // Check for ARIA properties that suggest interactivity
        const hasAriaProps = element.hasAttribute('aria-expanded') ||
            element.hasAttribute('aria-pressed') ||
            element.hasAttribute('aria-selected') ||
            element.hasAttribute('aria-checked');

        // Check for form-related functionality
        const isFormRelated = element.form !== undefined ||
            element.hasAttribute('contenteditable') ||
            style.userSelect !== 'none';

        // Check if element is draggable
        const isDraggable = element.draggable ||
            element.getAttribute('draggable') === 'true';

        return hasAriaProps ||
            // hasClickStyling ||
            hasClickHandler ||
            hasClickListeners ||
            // isFormRelated ||
            isDraggable;

    }

    // Helper function to check if element is visible
    function isElementVisible(element) {
        const style = window.getComputedStyle(element);
        return element.offsetWidth > 0 &&
            element.offsetHeight > 0 &&
            style.visibility !== 'hidden' &&
            style.display !== 'none';
    }

    // Helper function to check if element is the top element at its position
    function isTopElement(element) {
        // Find the correct document context and root element
        let doc = element.ownerDocument;

        // If we're in an iframe, elements are considered top by default
        if (doc !== window.document) {
            return true;
        }

        // For shadow DOM, we need to check within its own root context
        const shadowRoot = element.getRootNode();
        if (shadowRoot instanceof ShadowRoot) {
            const rect = element.getBoundingClientRect();
            const point = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };

            try {
                // Use shadow root's elementFromPoint to check within shadow DOM context
                const topEl = shadowRoot.elementFromPoint(point.x, point.y);
                if (!topEl) return false;

                // Check if the element or any of its parents match our target element
                let current = topEl;
                while (current && current !== shadowRoot) {
                    if (current === element) return true;
                    current = current.parentElement;
                }
                return false;
            } catch (e) {
                return true; // If we can't determine, consider it visible
            }
        }

        // Regular DOM elements
        const rect = element.getBoundingClientRect();
        const point = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };

        try {
            const topEl = document.elementFromPoint(point.x, point.y);
            if (!topEl) return false;

            let current = topEl;
            while (current && current !== document.documentElement) {
                if (current === element) return true;
                current = current.parentElement;
            }
            return false;
        } catch (e) {
            return true;
        }
    }

    // Helper function to check if text node is visible
    function isTextNodeVisible(textNode) {
        const range = document.createRange();
        range.selectNodeContents(textNode);
        const rect = range.getBoundingClientRect();

        return rect.width !== 0 &&
            rect.height !== 0 &&
            rect.top >= 0 &&
            rect.top <= window.innerHeight &&
            textNode.parentElement?.checkVisibility({
                checkOpacity: true,
                checkVisibilityCSS: true
            });
    }


    // Function to traverse the DOM and create nested JSON
    function buildDomTree(node, parentIframe = null) {
        if (!node) return null;

        // Special case for text nodes
        if (node.nodeType === Node.TEXT_NODE) {
            const textContent = node.textContent.trim();
            if (textContent && isTextNodeVisible(node)) {
                return {
                    type: "TEXT_NODE",
                    text: textContent,
                    isVisible: true,
                };
            }
            return null;
        }

        // Check if element is accepted
        if (node.nodeType === Node.ELEMENT_NODE && !isElementAccepted(node)) {
            return null;
        }

        const nodeData = {
            tagName: node.tagName ? node.tagName.toLowerCase() : null,
            attributes: {},
            xpath: node.nodeType === Node.ELEMENT_NODE ? getXPathTree(node, true) : null,
            children: [],
            pyneSelector: "",
        };

        // Copy all attributes if the node is an element
        if (node.nodeType === Node.ELEMENT_NODE && node.attributes) {
            // Use getAttributeNames() instead of directly iterating attributes
            const attributeNames = node.getAttributeNames?.() || [];
            for (const name of attributeNames) {
                nodeData.attributes[name] = node.getAttribute(name);
            }
        }

        if (node.nodeType === Node.ELEMENT_NODE) {
            const isInteractive = isInteractiveElement(node);
            const isVisible = isElementVisible(node);
            const isTop = isTopElement(node);

            nodeData.isInteractive = isInteractive;
            nodeData.isVisible = isVisible;
            nodeData.isTopElement = isTop;

            // Highlight if element meets all criteria and highlighting is enabled
            if (isInteractive && isVisible && isTop) {
                nodeData.highlightIndex = highlightIndex++;
                if (doHighlightElements) {
                    highlightElement(node, nodeData.highlightIndex, parentIframe);
                    nodeData.pyneSelector = generateSelector(node);
                }
            }
        }

        // Only add iframeContext if we're inside an iframe
        // if (parentIframe) {
        //     nodeData.iframeContext = `iframe[src="${parentIframe.src || ''}"]`;
        // }

        // Only add shadowRoot field if it exists
        if (node.shadowRoot) {
            nodeData.shadowRoot = true;
        }

        // Handle shadow DOM
        if (node.shadowRoot) {
            const shadowChildren = Array.from(node.shadowRoot.childNodes).map(child =>
                buildDomTree(child, parentIframe)
            );
            nodeData.children.push(...shadowChildren);
        }

        // Handle iframes
        if (node.tagName === 'IFRAME') {
            try {
                const iframeDoc = node.contentDocument || node.contentWindow.document;
                if (iframeDoc) {
                    const iframeChildren = Array.from(iframeDoc.body.childNodes).map(child =>
                        buildDomTree(child, node)
                    );
                    nodeData.children.push(...iframeChildren);
                }
            } catch (e) {
                console.warn('Unable to access iframe:', node);
            }
        } else {
            const children = Array.from(node.childNodes).map(child =>
                buildDomTree(child, parentIframe)
            );
            nodeData.children.push(...children);
        }

        return nodeData;
    }

    function generateSelector(element) {
        function getUniqueXpath(element) {
          const idPath = getById(element);
          if (idPath.length > 0) {
            return idPath;
          }
      
          const attrPath = getByAttribute(element);
          if (attrPath.length > 0) {
            return attrPath;
          }
      
          const textPath = getByText(element);
          if (textPath.length > 0) {
            return textPath;
          }
      
          const clsxPath = getByUniqueClass(element);
          if (clsxPath.length > 0) {
            return clsxPath;
          }
      
          const comboPath = getByClassCombo(element);
          if (comboPath.length > 0) {
            return comboPath;
          }
      
          return '';
        }
      
        function getById(element) {
          if (!element.id) return '';
      
          const xpath = `//*[@id="${element.id}"]`;
          if (isValidXPath(xpath) && isUnique(xpath, element)) {
            return xpath;
          }
      
          return '';
        }
      
        function getByAttribute(element) {
          const attributes = element.attributes || [];
          for (let i = 0; i < attributes.length; i++) {
            const { name, value } = attributes[i];
      
            console.log({ name, value });
      
            if (
              value.length === 0 ||
              (!name.startsWith('data-') &&
                !name.startsWith('aria-') &&
                name !== 'alt' &&
                name !== 'placeholder' &&
                name !== 'name')
            )
              continue;
      
            const xpath = x(`[@${name}="${value}"]`, element);
            if (xpath.length > 0) {
              return xpath;
            }
          }
      
          return '';
        }
      
        function getByUniqueClass(element) {
          if (!element.className) return '';
      
          const classList = Array.from(element.classList).filter(isValidClassName);
      
          for (let i = 0; i < classList.length; i++) {
            const xpath = x(`[contains(@class, "${classList[i]}")]`, element);
            if (xpath.length > 0) {
              return xpath;
            }
          }
      
          return '';
        }
      
        function getByText(element) {
          if (!element.textContent) return '';
      
          const allowedTags = ['a', 'button', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'li', 'label'];
          const tagName = getTagName(element);
          if(!tagName) {
            return '';
          }
          
          if (allowedTags.includes(tagName)) {
            const textContent = element?.textContent
              ?.split('\n')
              .sort((a, b) => b.length - a.length)[0]
              .trim()
              .replace(/"/g, '\'');
      
            if (textContent && textContent.length > 0) {
              const pathIndex = getElementIndexInParent(element);
              const xpathOptions = [
                `//*[contains(text(),"${textContent}")]`,
                `//*[text()="${textContent}"]`,
                `//*[contains(.,"${textContent}")]`,
                `//${tagName}[contains(text(),"${textContent}")]`,
                `//${tagName}[text()="${textContent}"]`,
                `//${tagName}[contains(.,"${textContent}")]`,
                `//${tagName}${pathIndex}[contains(text(),"${textContent}")]`,
                `//${tagName}${pathIndex}[text()="${textContent}"]`,
                `//${tagName}${pathIndex}[contains(.,"${textContent}")]`,
              ];
      
              const xpath = xpathOptions.find(xpath => isValidXPath(xpath) && isUnique(xpath, element));
              return xpath || '';
            }
          }
      
          return '';
        }
      
        function getByClassCombo(element) {
          if (!element.className) return '';
      
          const classList = Array.from(element.classList).filter(isValidClassName);
          const combinations = getClassCombinations(classList);
          // console.log({ combinations });
          for (const combo of combinations) {
            if (combo.length === 1) continue;
            // const selector = combo.map(c => '.' + c).join('');
            const attr = combo.map(c => `contains(@class,"${c}")`).join(' and ');
            const xpath = x(`[${attr}]`, element);
            if (xpath.length > 0) {
              return xpath;
            }
          }
      
          return '';
        }
      
        function getClassCombinations(classes) {
          const combinations = [];
          const n = classes.length;
          for (let i = 0; i < n; i++) {
            combinations.push([classes[i]]);
            for (let j = i + 1; j < n; j++) {
              combinations.push([classes[i], classes[j]]);
              for (let k = j + 1; k < n; k++) {
                combinations.push([classes[i], classes[j], classes[k]]);
              }
            }
          }
          return combinations;
        }
      
        function x(attr, element) {
          const tagName = getTagName(element);
          if(!tagName) {
            return '';
          }

          const pathIndex = getElementIndexInParent(element);
      
          let xpath = '//' + tagName + attr;
          if (isValidXPath(xpath) && isUnique(xpath, element)) {   
            return xpath;
          }
      
          xpath = '//' + tagName + pathIndex + attr;
          if (isValidXPath(xpath) && isUnique(xpath, element)) {
            return xpath;
          }
      
          return '';
        }
      
        function getTagName(element) {
          return element.tagName?.toLowerCase();
        }
      
        function getElementIndexInParent(el) {
          const siblings = Array.from(el.parentNode?.children || []).filter(e => e.tagName === el.tagName);
          if (siblings.length > 1) {
            // Return 1-based index if there are siblings with the same tag
            return `[${siblings.indexOf(el) + 1}]`;
          }
          return ''; // No need for index if it's unique within its parent
        }
      
        function isValidClassName(className) {
          // Reject class names that are too short
          if (className.length <= 2) return false;
          // Reject class names that contain digits
          if (/\d/.test(className)) return false;
          // Reject class names that start with known prefixes
          const rejectedPrefixes = ['css', 'jsx', 'tw', 'tailwind', 'Styled', 'style'];
          for (const prefix of rejectedPrefixes) {
            if (className.startsWith(prefix)) return false;
          }
          // Reject common utility class names
          const rejectedClassNames = [
            'my',
            'mx',
            'mt',
            'mb',
            'ml',
            'mr',
            'p',
            'py',
            'px',
            'pt',
            'pb',
            'pl',
            'pr',
            'flex',
            'grid',
            'inline',
            'block',
            'hidden',
            'relative',
            'absolute',
            'fixed',
            'static',
            'sticky',
            'top',
            'bottom',
            'left',
            'right',
            'font',
            'leading',
            'tracking',
            'uppercase',
            'lowercase',
            'capitalize',
            'antialiased',
            'break',
            'whitespace',
            'truncate',
            'cursor',
            'pointer',
            'hover',
            'focus',
            'active',
            'visited',
            'disabled',
            'first',
            'last',
            'even',
            'odd',
            'col',
            'row',
            'gap',
            'space',
            'divide',
            'border',
            'rounded',
            'shadow',
            'opacity',
            'transition',
            'duration',
            'ease',
            'delay',
            'animate',
            'fill',
            'stroke',
            'transform',
            'scale',
            'rotate',
            'translate',
            'skew',
            'origin',
            'resize',
            'appearance',
            'outline',
            'table',
            'select',
            'svg',
            'filter',
            'blend',
            'isolation',
            'mix',
            'order',
            'placeholder',
            'ring',
            'float',
            'clear',
            'object',
            'overflow',
            'position',
            'z',
            'display',
            'text',
            'bg',
            'w',
            'h',
            'min',
            'max',
            'inset',
            'm',
            'p',
            'bg',
            'text',
            'border',
            'grow',
            'shrink',
            'justify',
            'items',
            'align',
          ];
          if (rejectedClassNames.some(cn => cn === className || className.startsWith(cn + '-'))) return false;
      
          return true;
        }
      
        function isUnique(xpath, element) {
          if (
            document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue === element
          ) {
            return true;
          }
      
          return false;
        }

        function isValidXPath(xpath) {
          try {
            document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
            return true;
          } catch (e) {
            return false;
          }
        }
      
        return getUniqueXpath(element);
      }
      


    return buildDomTree(document.body);
}