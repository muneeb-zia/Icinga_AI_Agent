import os

header = """// SPDX-FileCopyrightText: 2023 Icinga GmbH <https://icinga.com>
// SPDX-License-Identifier: GPL-3.0-or-later

;(function () {
    let html = document.documentElement;
    window.name = html.dataset.icingaWindowName;
    window.icinga = new Icinga({
        baseUrl: html.dataset.icingaBaseUrl,
        locale: html.lang,
        timezone: html.dataset.icingaTimezone
    });

    if (! ('icingaIsIframe' in document.documentElement.dataset)) {
        html.classList.replace('no-js', 'js');
    }

    if (window.getComputedStyle) {
        let matched;
        let element = document.getElementById('layout');
        let name = window
            .getComputedStyle(html)['font-family']
            .replace(/['",]/g, '');

        if (null !== (matched = name.match(/^([a-z]+)-layout$/))) {
            element.classList.replace('default-layout', name);
            if ('object' === typeof window.console) {
                window.console.log('Icinga Web 2: setting initial layout to ' + name);
            }
        }
    }
})();

"""

module_path = os.path.join('icinga-module-ai', 'public', 'js', 'module.js')
bootstrap_path = os.path.join('icinga-module-ai', 'public', 'js', 'bootstrap_fixed.js')

with open(module_path, 'r', encoding='utf-8') as f:
    module_code = f.read()

with open(bootstrap_path, 'w', encoding='utf-8') as f:
    f.write(header + '\n' + module_code)

print(f"Successfully generated {bootstrap_path} ({len(header) + len(module_code)} chars)")
