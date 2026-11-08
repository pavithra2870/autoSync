"""UI + advisor strings. English and Hindi are hand-written; other languages are translated once by the
local model (scripts/warm_i18n.py), cached as JSON in app/i18n_cache and committed, so nothing waits at demo time.
Prices, product names and eligibility messages never come from the LLM."""
import json
import re
import threading

from .config import I18N_CACHE_DIR
from .llm import LANG_NAMES, available, translate_strings

EN = {
    "app.title": "Accel Business", "app.tagline": "Get your business online in one sitting",
    "lang.choose": "Choose your language",
    "step.chat": "Advisor", "step.quote": "Your plan", "step.kyc": "Verify", "step.confirm": "Confirm", "step.track": "Track",
    "common.continue": "Continue", "common.back": "Back", "common.skip": "Skip", "common.send": "Send",
    "common.type_here": "Type your answer…", "common.loading": "Loading…", "common.yes": "Yes", "common.no": "No",
    "mode.ai": "AI advisor", "mode.rules": "Simple mode",
    "chat.greeting": "Namaste! I'm your Accel Business advisor. Answer a few quick questions and watch your pack build up at the top, with one clear monthly price.",
    "chat.typing": "Thinking…",
    "chat.retry": "Sorry, I didn't catch that. Please pick an option or type again.",
    "chat.human": "No problem. I'll ask a local Accel Business partner to call you. You can keep going here meanwhile.",
    "chat.done": "Thanks! Your plan is ready, with special offers for signing up online.",
    "chat.city_unverified": "I don't have your city in my service list, so a partner will confirm availability.",
    "chat.pack": "Your pack so far", "chat.pack_empty": "Tell me about your business and your pack starts here",
    "chat.left": "{n} quick questions left", "chat.left1": "Last question", "chat.see_plan": "See my plan and offers",
    "chat.about": "about",
    "q.segment": "What kind of business do you run?",
    "q.city": "Which city is your business in?",
    "q.employees": "How many people work in your business?",
    "q.sites": "How many locations (shops, offices or units) do you have?",
    "q.internet": "What internet do you use today?",
    "q.gst": "Do you have a GST or Udyam registration?",
    "q.needs": "What troubles your business most today? Pick all that apply.",
    "q.spend": "Roughly how much do you spend on phone and internet each month?",
    "seg.micro": "Shop, salon or small service", "seg.prof": "Clinic, office or coaching",
    "seg.multi": "3+ outlets (restaurant, retail chain, hotel)", "seg.mfg": "Factory or workshop",
    "net.business": "Business broadband", "net.home": "Home broadband", "net.hotspot": "Mobile hotspot",
    "net.leased": "Leased line", "net.mixed": "Different ISP per site", "net.none": "None",
    "gst.yes": "Yes, I have GST", "gst.udyam": "Only Udyam", "gst.none": "Neither yet",
    "need.cctv": "CCTV cameras", "need.whatsapp": "WhatsApp for customers", "need.pos": "Billing / POS",
    "need.security": "Security & backup", "need.phone": "Business phone / IVR", "need.website": "Website",
    "need.none": "Nothing specific",
    "pain.uptime": "Internet keeps going down", "pain.pos": "Billing and UPI hassles",
    "pain.cctv": "Can't keep an eye on my place when away", "pain.whatsapp": "Customers can't reach me easily",
    "pain.website": "Customers can't find me online", "pain.security": "Worried about losing data or viruses",
    "pain.phone": "Missing customer calls", "pain.bills": "Too many bills and helplines",
    "pain.iot": "Machines stop without warning", "pain.fleet": "Don't know where my vehicles are",
    "pain.backup": "Afraid of losing important files",
    "item.internet_core": "Business internet", "item.leased": "Dedicated line", "item.mobile_lines": "Mobile lines",
    "item.email_cloud": "Business email", "item.data_security": "Virus protection", "item.backup": "Cloud backup",
    "item.failover_sites": "Backup internet", "item.sdwan": "All-sites network", "item.pos": "Billing and UPI",
    "item.cctv": "CCTV on phone", "item.whatsapp": "WhatsApp Business", "item.firewall": "Firewall",
    "item.iot": "Machine alerts", "item.phone_system": "Business phone", "item.wifi": "Secure Wi-Fi",
    "item.website": "Website", "item.static_ip": "Fixed IP", "item.fleet": "Vehicle GPS", "item.alt_internet": "Internet",
    "reveal.title": "Building your plan…", "reveal.1": "Matched your answers to 25 services",
    "reveal.2": "Checked what {n} businesses like yours chose", "reveal.3": "Added your online sign-up offers",
    "biz.micro": "shop", "biz.prof": "office", "biz.multi": "business", "biz.mfg": "factory",
    "quote.made_for": "Made for your {business}","quote.in_city": "in {city}",
    "quote.per_day": "Just ₹{n} a day", "quote.separately": "a month if bought separately", "common.per_month": "/month",
    "quote.held": "This price is held for you until {date}",
    "tier.title": "Pick your pack", "tier.basic": "Basic", "tier.recommended": "Recommended", "tier.complete": "Complete",
    "tier.popular": "Most chosen", "tier.items": "{n} services", "tier.custom": "Your own mix",
    "fix.title": "You told us. Here's the fix.", "fix.bills": "One bill and one helpline for everything",
    "fix.today": "Today: {x}", "fix.add": "Add", "fix.included": "Included",
    "cmp.title": "Why one pack beats buying separately", "cmp.separately": "Buying separately", "cmp.pack": "Accel pack",
    "cmp.money": "Cost in year one", "cmp.hassle": "Hassle", "cmp.time": "Getting started",
    "cmp.providers": "{n} providers, {n} bills, {n} helplines", "cmp.one": "1 bill, 1 helpline, 1 team",
    "cmp.time_old": "~{days} days of visits and paperwork, ~{calls} follow-up calls",
    "cmp.time_new": "Done today in one sitting, live in ~{n} days, updates on WhatsApp",
    "cmp.save": "You save ₹{n} in year one", "cmp.months_free": "That's like {n} months free",
    "cmp.month_free": "That's like 1 month free",
    "cmp.how": "How we worked this out",
    "cmp.how_text": "Buying separately means the same services bought one by one at our standard list rate (the top of our price range), with full setup fees. The pack cost is your price above, minus the online sign-up offers. Days and calls are averages from our own sales records for businesses like yours.",
    "spend.less": "₹{n} a month less than you pay today", "spend.more": "Only about ₹{n} a day more than you pay today",
    "spend.gets": "and you also get {items}",
    "offer.title": "Online sign-up offers", "offer.sub": "Only when you sign up here. No salesperson needed.",
    "offer.setup": "Free setup", "offer.setup_part": "₹{n} off setup", "offer.setup_d": "Save ₹{n} on installation",
    "offer.half": "First month half price", "offer.half_part": "₹{n} off first month", "offer.half_d": "Save ₹{n}",
    "offer.switch": "Switch with no downtime", "offer.switch_d": "Keep your old connection until ours is live. We handle the switch.",
    "offer.lang": "Help in {language}", "offer.lang_d": "A helpline and a local partner who speak your language",
    "offer.ontime": "On-time promise", "offer.ontime_d": "Live in {n} working days, or 1 week free",
    "offer.exit": "30-day easy exit", "offer.exit_d": "Not happy in the first 30 days? Cancel with no fee.",
    "offer.lock": "Price locked", "offer.lock_d": "Same monthly price for all {n} months",
    "proof.segment": "{n} businesses like yours already use Accel", "proof.city": "{n} of them in {city}",
    "quote.reassure": "No payment now · Cancel free in 30 days", "quote.get": "Get this pack",
    "confirm.offers": "Online offers applied", "confirm.first_month": "First month (after offer)",
    "confirm.setup_after": "Setup (after offer)",
    "quote.title": "Your plan", "quote.monthly": "Monthly price", "quote.setup": "One-time setup",
    "quote.contract": "Contract", "quote.months": "{n} months", "quote.excl": "Prices exclude GST",
    "quote.included": "In your plan", "quote.addons": "Add-ons", "quote.why": "Why this plan",
    "quote.install": "Service live in about {n} days", "quote.compare": "You spend about ₹{spend} a month today",
    "quote.accept": "Accept and continue", "quote.each": "per {unit}", "quote.longer": "Choose 24 months for a lower monthly price",
    "quote.swap": "Other speeds", "quote.pending": "Needs GST check", "quote.range": "Range ₹{min}–₹{max}",
    "why.internet_core": "Reliable internet for your business",
    "why.leased": "A dedicated line with an uptime guarantee",
    "why.mobile_lines": "Business mobile lines for you and your team",
    "why.email_cloud": "Business email and documents on your own domain",
    "why.data_security": "Protects customer and patient data",
    "why.backup": "Automatic backup of important files",
    "why.failover_sites": "Keeps every site online if the main link fails",
    "why.sdwan": "One bill and one control panel for all your sites",
    "why.pos": "Billing and UPI on one tablet", "why.cctv": "See your shop from your phone",
    "why.whatsapp": "Reach customers on WhatsApp", "why.firewall": "Managed security for your network",
    "why.iot": "Track machine uptime and power use", "why.phone_system": "Business phone lines and IVR over the internet",
    "why.wifi": "Secure Wi-Fi with a guest network", "why.website": "Website and domain",
    "why.static_ip": "Fixed IP for CCTV or remote access", "why.fleet": "Live GPS tracking for vehicles",
    "why.alt_internet": "Another speed option",
    "lock.needs_gstin": "Needs a GST registration", "lock.min_employees": "For businesses with {n}+ people",
    "lock.min_sites": "For businesses with {n}+ locations", "lock.tier": "Not available in your city yet",
    "lock.needs_base": "Needs an internet plan in the bundle", "lock.pending_gst": "Unlocks once your GST is verified",
    "kyc.title": "Verify your business",
    "kyc.consent.title": "Before we collect your documents",
    "kyc.consent.purpose": "We use your documents only to verify your business and activate your service.",
    "kyc.consent.data": "We collect: GST certificate, Udyam certificate, ID of the signatory and address proof.",
    "kyc.consent.retain": "Document photos are read and deleted straight away. We keep only the extracted details: 90 days after activation, or 30 days if you do not go ahead.",
    "kyc.consent.rights": "You can withdraw consent or ask us to erase your data at any time.",
    "kyc.consent.agree": "I agree", "kyc.consent.decline": "No thanks",
    "kyc.lookup.title": "Quick lookup", "kyc.gstin": "GSTIN", "kyc.udyam": "Udyam number", "kyc.lookup": "Look up",
    "kyc.found": "Found: {name}", "kyc.notfound": "Not found in the registry", "kyc.status": "Status: {status}",
    "kyc.doc.gst": "GST certificate", "kyc.doc.udyam": "Udyam certificate", "kyc.doc.id": "Signatory ID",
    "kyc.doc.address": "Address proof (bill, last 90 days)",
    "kyc.upload": "Upload", "kyc.sample": "Try a sample applicant", "kyc.verify": "Check my documents",
    "kyc.checking": "Reading your documents…", "kyc.replace": "Replace",
    "verdict.verified": "All good. Your business is verified.",
    "verdict.action": "Almost there. Please fix the items below.",
    "verdict.review": "Our team will review this quickly and call you.",
    "verdict.blocked": "We can't go ahead with this registration.",
    "chk.completeness": "All documents provided", "chk.quality": "Document is clear enough to read",
    "chk.doc_type": "Right document uploaded", "chk.gstin_valid": "GSTIN format is valid",
    "chk.gstin_registry": "GSTIN found in registry", "chk.gstin_status": "GSTIN is active",
    "chk.gst_name": "Name on GST matches the registry", "chk.gst_address": "GST address matches the registry",
    "chk.udyam_number": "Udyam number is on the certificate", "chk.udyam_registry": "Udyam number found in registry",
    "chk.udyam_name": "Udyam name matches", "chk.signatory": "Signatory is authorised",
    "chk.id_valid": "ID is still valid", "chk.address_fresh": "Address proof is within 90 days",
    "chk.address_match": "Address proof matches business name and address",
    "chk.name_consistent": "Business name is the same on every document",
    "chk.autocorrected": "We corrected a misread number. Please confirm it.",
    "confirm.title": "Review and sign", "confirm.sign": "Type your full name to sign",
    "confirm.agree": "I accept the plan and terms", "confirm.place": "Place order",
    "confirm.held": "On hold until GST is verified",
    "track.title": "Order tracker", "track.order": "Order {id}", "track.expected": "Expected {date}",
    "track.simulate": "Demo: move to next step", "track.messages": "Messages sent to you",
    "track.nocall": "No need to call us. This page updates by itself.", "track.done": "Done",
    "stage.quote": "Plan accepted", "stage.kyc": "Documents verified", "stage.sign": "Agreement signed",
    "stage.install_sched": "Installation scheduled", "stage.installing": "Installation in progress",
    "stage.active": "Service active",
    "err.generic": "Something went wrong. Please try again.",
    "explain.template": "For your {business} ({staff} people, {city}), this plan covers {items} for one monthly price of ₹{total}.",
}

HI = {
    "app.tagline": "अपने बिज़नेस को एक ही बार में डिजिटल बनाएँ", "lang.choose": "अपनी भाषा चुनें",
    "step.chat": "सलाहकार", "step.quote": "आपका प्लान", "step.kyc": "सत्यापन", "step.confirm": "पुष्टि", "step.track": "ट्रैक",
    "common.continue": "आगे बढ़ें", "common.back": "वापस", "common.skip": "छोड़ें", "common.send": "भेजें",
    "common.type_here": "अपना जवाब लिखें…", "common.loading": "लोड हो रहा है…", "common.yes": "हाँ", "common.no": "नहीं",
    "mode.ai": "AI सलाहकार", "mode.rules": "सरल मोड",
    "chat.greeting": "नमस्ते! मैं आपका Accel Business सलाहकार हूँ। कुछ छोटे सवालों के जवाब दीजिए और ऊपर अपना पैक बनते देखिए, एक साफ़ मासिक कीमत के साथ।",
    "chat.typing": "सोच रहा हूँ…",
    "chat.retry": "माफ़ कीजिए, मैं समझ नहीं पाया। कृपया कोई विकल्प चुनें या दोबारा लिखें।",
    "chat.human": "कोई बात नहीं। मैं स्थानीय Accel Business पार्टनर से आपको कॉल करने के लिए कहूँगा। तब तक आप यहीं आगे बढ़ सकते हैं।",
    "chat.done": "धन्यवाद! आपका प्लान तैयार है, ऑनलाइन जुड़ने पर ख़ास ऑफ़र के साथ।",
    "chat.city_unverified": "आपका शहर मेरी सेवा-सूची में नहीं है, इसलिए पार्टनर उपलब्धता की पुष्टि करेगा।",
    "chat.pack": "अब तक आपका पैक", "chat.pack_empty": "अपने बिज़नेस के बारे में बताइए, आपका पैक यहीं बनना शुरू होगा",
    "chat.left": "बस {n} छोटे सवाल बाकी", "chat.left1": "आख़िरी सवाल", "chat.see_plan": "मेरा प्लान और ऑफ़र देखें",
    "chat.about": "लगभग",
    "q.segment": "आप किस तरह का बिज़नेस चलाते हैं?", "q.city": "आपका बिज़नेस किस शहर में है?",
    "q.employees": "आपके यहाँ कितने लोग काम करते हैं?", "q.sites": "आपकी कितनी जगहें (दुकान, ऑफिस या यूनिट) हैं?",
    "q.internet": "अभी आप कौन सा इंटरनेट इस्तेमाल करते हैं?", "q.gst": "क्या आपके पास GST या उद्यम रजिस्ट्रेशन है?",
    "q.needs": "आज आपके बिज़नेस में सबसे ज़्यादा परेशानी किस बात की है? जितने चाहें चुनें।", "q.spend": "फ़ोन और इंटरनेट पर हर महीने लगभग कितना ख़र्च होता है?",
    "seg.micro": "दुकान, सैलून या छोटी सर्विस", "seg.prof": "क्लिनिक, ऑफिस या कोचिंग",
    "seg.multi": "3+ आउटलेट (रेस्टोरेंट, रिटेल चेन, होटल)", "seg.mfg": "फ़ैक्टरी या वर्कशॉप",
    "net.business": "बिज़नेस ब्रॉडबैंड", "net.home": "घरेलू ब्रॉडबैंड", "net.hotspot": "मोबाइल हॉटस्पॉट",
    "net.leased": "लीज़्ड लाइन", "net.mixed": "हर जगह अलग ISP", "net.none": "कुछ नहीं",
    "gst.yes": "हाँ, GST है", "gst.udyam": "सिर्फ़ उद्यम", "gst.none": "अभी कुछ नहीं",
    "need.cctv": "CCTV कैमरा", "need.whatsapp": "ग्राहकों के लिए WhatsApp", "need.pos": "बिलिंग / POS",
    "need.security": "सिक्योरिटी और बैकअप", "need.phone": "बिज़नेस फ़ोन / IVR", "need.website": "वेबसाइट",
    "need.none": "कुछ ख़ास नहीं",
    "pain.uptime": "इंटरनेट बार-बार बंद हो जाता है", "pain.pos": "बिलिंग और UPI की दिक्कत",
    "pain.cctv": "बाहर रहने पर दुकान/ऑफिस पर नज़र नहीं रख पाता", "pain.whatsapp": "ग्राहक मुझसे आसानी से संपर्क नहीं कर पाते",
    "pain.website": "ग्राहक मुझे ऑनलाइन नहीं ढूँढ पाते", "pain.security": "डेटा खोने या वायरस का डर",
    "pain.phone": "ग्राहकों की कॉल छूट जाती हैं", "pain.bills": "बहुत सारे बिल और हेल्पलाइन",
    "pain.iot": "मशीनें बिना चेतावनी रुक जाती हैं", "pain.fleet": "पता नहीं मेरी गाड़ियाँ कहाँ हैं",
    "pain.backup": "ज़रूरी फ़ाइलें खोने का डर",
    "item.internet_core": "बिज़नेस इंटरनेट", "item.leased": "डेडिकेटेड लाइन", "item.mobile_lines": "मोबाइल लाइनें",
    "item.email_cloud": "बिज़नेस ईमेल", "item.data_security": "वायरस से सुरक्षा", "item.backup": "क्लाउड बैकअप",
    "item.failover_sites": "बैकअप इंटरनेट", "item.sdwan": "सभी जगहों का नेटवर्क", "item.pos": "बिलिंग और UPI",
    "item.cctv": "फ़ोन पर CCTV", "item.whatsapp": "WhatsApp Business", "item.firewall": "फ़ायरवॉल",
    "item.iot": "मशीन अलर्ट", "item.phone_system": "बिज़नेस फ़ोन", "item.wifi": "सुरक्षित Wi-Fi",
    "item.website": "वेबसाइट", "item.static_ip": "फ़िक्स्ड IP", "item.fleet": "गाड़ी GPS", "item.alt_internet": "इंटरनेट",
    "reveal.title": "आपका प्लान बन रहा है…", "reveal.1": "आपके जवाबों को 25 सेवाओं से मिलाया",
    "reveal.2": "देखा कि आप जैसे {n} बिज़नेस ने क्या चुना", "reveal.3": "ऑनलाइन जुड़ने के ऑफ़र जोड़े",
    "biz.micro": "दुकान", "biz.prof": "ऑफिस", "biz.multi": "बिज़नेस", "biz.mfg": "फ़ैक्टरी",
    "quote.made_for": "आपके बिज़नेस के लिए: {business}","quote.in_city": "· {city}",
    "quote.per_day": "सिर्फ़ ₹{n} रोज़", "quote.separately": "महीना, अलग-अलग ख़रीदने पर", "common.per_month": "/महीना",
    "quote.held": "यह कीमत {date} तक आपके लिए रोकी गई है",
    "tier.title": "अपना पैक चुनें", "tier.basic": "बेसिक", "tier.recommended": "सुझाया गया", "tier.complete": "पूरा पैक",
    "tier.popular": "सबसे ज़्यादा चुना गया", "tier.items": "{n} सेवाएँ", "tier.custom": "आपका अपना मिक्स",
    "fix.title": "आपने बताया, हमने हल किया", "fix.bills": "हर चीज़ के लिए एक बिल और एक हेल्पलाइन",
    "fix.today": "अभी: {x}", "fix.add": "जोड़ें", "fix.included": "शामिल",
    "cmp.title": "अलग-अलग ख़रीदने से एक पैक बेहतर क्यों", "cmp.separately": "अलग-अलग ख़रीदें", "cmp.pack": "Accel पैक",
    "cmp.money": "पहले साल का ख़र्च", "cmp.hassle": "झंझट", "cmp.time": "शुरुआत",
    "cmp.providers": "{n} कंपनियाँ, {n} बिल, {n} हेल्पलाइन", "cmp.one": "1 बिल, 1 हेल्पलाइन, 1 टीम",
    "cmp.time_old": "~{days} दिन विज़िट और कागज़ी काम, ~{calls} बार फ़ॉलो-अप कॉल",
    "cmp.time_new": "आज ही एक बार में पूरा, ~{n} दिन में चालू, WhatsApp पर अपडेट",
    "cmp.save": "पहले साल में ₹{n} की बचत", "cmp.months_free": "यानी लगभग {n} महीने मुफ़्त",
    "cmp.month_free": "यानी लगभग 1 महीना मुफ़्त",
    "cmp.how": "हमने यह कैसे निकाला",
    "cmp.how_text": "अलग-अलग ख़रीदने का मतलब है यही सेवाएँ एक-एक करके हमारी स्टैंडर्ड लिस्ट रेट (कीमत रेंज का ऊपरी हिस्सा) पर, पूरी सेटअप फ़ीस के साथ। पैक का ख़र्च ऊपर दी गई आपकी कीमत है, ऑनलाइन ऑफ़र घटाकर। दिन और कॉल आप जैसे बिज़नेस के लिए हमारे अपने सेल्स रिकॉर्ड का औसत हैं।",
    "spend.less": "आज के ख़र्च से ₹{n} महीना कम", "spend.more": "आज के ख़र्च से सिर्फ़ लगभग ₹{n} रोज़ ज़्यादा",
    "spend.gets": "और साथ में मिलेगा {items}",
    "offer.title": "ऑनलाइन जुड़ने के ऑफ़र", "offer.sub": "सिर्फ़ यहाँ ऑनलाइन जुड़ने पर। किसी सेल्समैन की ज़रूरत नहीं।",
    "offer.setup": "सेटअप मुफ़्त", "offer.setup_part": "सेटअप पर ₹{n} की छूट", "offer.setup_d": "इंस्टॉलेशन पर ₹{n} बचाएँ",
    "offer.half": "पहला महीना आधी कीमत पर", "offer.half_part": "पहले महीने ₹{n} की छूट", "offer.half_d": "₹{n} बचाएँ",
    "offer.switch": "बिना रुकावट बदलें", "offer.switch_d": "हमारी सेवा चालू होने तक पुराना कनेक्शन रखें। बदलाव हम संभालेंगे।",
    "offer.lang": "{language} में मदद", "offer.lang_d": "आपकी भाषा बोलने वाली हेल्पलाइन और लोकल पार्टनर",
    "offer.ontime": "समय पर चालू होने का वादा", "offer.ontime_d": "{n} कामकाजी दिन में चालू, नहीं तो 1 हफ़्ता मुफ़्त",
    "offer.exit": "30 दिन में आसान वापसी", "offer.exit_d": "पहले 30 दिन में पसंद नहीं आया? बिना फ़ीस बंद करें।",
    "offer.lock": "कीमत तय", "offer.lock_d": "पूरे {n} महीने वही मासिक कीमत",
    "proof.segment": "आप जैसे {n} बिज़नेस पहले से Accel इस्तेमाल करते हैं", "proof.city": "इनमें से {n} {city} में",
    "quote.reassure": "अभी कोई भुगतान नहीं · 30 दिन में मुफ़्त रद्द", "quote.get": "यह पैक लें",
    "confirm.offers": "लगाए गए ऑनलाइन ऑफ़र", "confirm.first_month": "पहला महीना (ऑफ़र के बाद)",
    "confirm.setup_after": "सेटअप (ऑफ़र के बाद)",
    "quote.title": "आपका प्लान", "quote.monthly": "मासिक कीमत", "quote.setup": "एकमुश्त सेटअप",
    "quote.contract": "अनुबंध", "quote.months": "{n} महीने", "quote.excl": "कीमतों में GST शामिल नहीं है",
    "quote.included": "आपके प्लान में", "quote.addons": "ऐड-ऑन", "quote.why": "यह प्लान क्यों",
    "quote.install": "सेवा लगभग {n} दिन में चालू", "quote.compare": "आप अभी हर महीने लगभग ₹{spend} ख़र्च करते हैं",
    "quote.accept": "प्लान स्वीकार करें", "quote.each": "प्रति {unit}", "quote.longer": "कम मासिक कीमत के लिए 24 महीने चुनें",
    "quote.swap": "दूसरी स्पीड", "quote.pending": "GST जाँच बाकी", "quote.range": "रेंज ₹{min}–₹{max}",
    "why.internet_core": "आपके बिज़नेस के लिए भरोसेमंद इंटरनेट",
    "why.leased": "अपटाइम गारंटी वाली डेडिकेटेड लाइन",
    "why.mobile_lines": "आपके और आपकी टीम के लिए बिज़नेस मोबाइल लाइन",
    "why.email_cloud": "अपने डोमेन पर बिज़नेस ईमेल और डॉक्यूमेंट",
    "why.data_security": "ग्राहकों और मरीज़ों के डेटा की सुरक्षा",
    "why.backup": "ज़रूरी फ़ाइलों का ऑटोमैटिक बैकअप",
    "why.failover_sites": "मुख्य लाइन बंद होने पर भी हर जगह इंटरनेट चालू",
    "why.sdwan": "सभी जगहों के लिए एक बिल और एक कंट्रोल पैनल",
    "why.pos": "एक टैबलेट पर बिलिंग और UPI", "why.cctv": "अपनी दुकान फ़ोन पर देखें",
    "why.whatsapp": "WhatsApp पर ग्राहकों तक पहुँचें", "why.firewall": "आपके नेटवर्क की मैनेज्ड सिक्योरिटी",
    "why.iot": "मशीनों का अपटाइम और बिजली खपत ट्रैक करें", "why.phone_system": "इंटरनेट पर बिज़नेस फ़ोन लाइन और IVR",
    "why.wifi": "सुरक्षित Wi-Fi और ग्राहकों के लिए गेस्ट नेटवर्क", "why.website": "वेबसाइट और डोमेन",
    "why.static_ip": "CCTV या रिमोट एक्सेस के लिए फ़िक्स्ड IP", "why.fleet": "गाड़ियों की लाइव GPS ट्रैकिंग",
    "why.alt_internet": "दूसरी स्पीड का विकल्प",
    "lock.needs_gstin": "GST रजिस्ट्रेशन ज़रूरी", "lock.min_employees": "{n}+ लोगों वाले बिज़नेस के लिए",
    "lock.min_sites": "{n}+ जगहों वाले बिज़नेस के लिए", "lock.tier": "आपके शहर में अभी उपलब्ध नहीं",
    "lock.needs_base": "बंडल में इंटरनेट प्लान ज़रूरी", "lock.pending_gst": "GST सत्यापित होने पर चालू",
    "kyc.title": "अपने बिज़नेस का सत्यापन", "kyc.consent.title": "दस्तावेज़ लेने से पहले",
    "kyc.consent.purpose": "हम आपके दस्तावेज़ सिर्फ़ बिज़नेस सत्यापन और सेवा चालू करने के लिए इस्तेमाल करते हैं।",
    "kyc.consent.data": "हम ये लेते हैं: GST प्रमाणपत्र, उद्यम प्रमाणपत्र, हस्ताक्षरकर्ता का ID और पते का प्रमाण।",
    "kyc.consent.retain": "दस्तावेज़ की फ़ोटो पढ़ते ही हटा दी जाती है। हम सिर्फ़ निकाली गई जानकारी रखते हैं: सेवा चालू होने के बाद 90 दिन, या ऑर्डर पूरा न होने पर 30 दिन।",
    "kyc.consent.rights": "आप कभी भी सहमति वापस ले सकते हैं या अपना डेटा मिटाने को कह सकते हैं।",
    "kyc.consent.agree": "मैं सहमत हूँ", "kyc.consent.decline": "नहीं, धन्यवाद",
    "kyc.lookup.title": "तुरंत जाँच", "kyc.udyam": "उद्यम नंबर", "kyc.lookup": "खोजें",
    "kyc.found": "मिला: {name}", "kyc.notfound": "रजिस्ट्री में नहीं मिला", "kyc.status": "स्थिति: {status}",
    "kyc.doc.gst": "GST प्रमाणपत्र", "kyc.doc.udyam": "उद्यम प्रमाणपत्र", "kyc.doc.id": "हस्ताक्षरकर्ता का ID",
    "kyc.doc.address": "पते का प्रमाण (बिल, पिछले 90 दिन)",
    "kyc.upload": "अपलोड करें", "kyc.sample": "नमूना आवेदक आज़माएँ", "kyc.verify": "मेरे दस्तावेज़ जाँचें",
    "kyc.checking": "आपके दस्तावेज़ पढ़ रहे हैं…", "kyc.replace": "बदलें",
    "verdict.verified": "सब ठीक है। आपका बिज़नेस सत्यापित हो गया।",
    "verdict.action": "लगभग हो गया। कृपया नीचे की बातें ठीक करें।",
    "verdict.review": "हमारी टीम इसे जल्दी देखकर आपको कॉल करेगी।",
    "verdict.blocked": "हम इस रजिस्ट्रेशन के साथ आगे नहीं बढ़ सकते।",
    "chk.completeness": "सभी दस्तावेज़ मौजूद हैं", "chk.quality": "दस्तावेज़ साफ़ पढ़ने लायक है",
    "chk.doc_type": "सही दस्तावेज़ अपलोड हुआ", "chk.gstin_valid": "GSTIN का फ़ॉर्मेट सही है",
    "chk.gstin_registry": "GSTIN रजिस्ट्री में मिला", "chk.gstin_status": "GSTIN चालू है",
    "chk.gst_name": "GST पर नाम रजिस्ट्री से मेल खाता है", "chk.gst_address": "GST का पता रजिस्ट्री से मेल खाता है",
    "chk.udyam_number": "उद्यम प्रमाणपत्र पर नंबर मौजूद है", "chk.udyam_registry": "उद्यम नंबर रजिस्ट्री में मिला",
    "chk.udyam_name": "उद्यम पर नाम मेल खाता है", "chk.signatory": "हस्ताक्षरकर्ता अधिकृत है",
    "chk.id_valid": "ID अभी वैध है", "chk.address_fresh": "पते का प्रमाण 90 दिन के भीतर का है",
    "chk.address_match": "पते का प्रमाण बिज़नेस के नाम और पते से मेल खाता है",
    "chk.name_consistent": "सभी दस्तावेज़ों पर बिज़नेस का नाम एक जैसा है",
    "chk.autocorrected": "पढ़ा गया एक नंबर हमने ठीक किया है। कृपया पुष्टि करें।",
    "confirm.title": "देखें और हस्ताक्षर करें", "confirm.sign": "हस्ताक्षर के लिए अपना पूरा नाम लिखें",
    "confirm.agree": "मैं प्लान और शर्तें स्वीकार करता/करती हूँ", "confirm.place": "ऑर्डर करें",
    "confirm.held": "GST सत्यापन तक रोका गया",
    "track.title": "ऑर्डर ट्रैकर", "track.order": "ऑर्डर {id}", "track.expected": "अपेक्षित {date}",
    "track.simulate": "डेमो: अगला चरण", "track.messages": "आपको भेजे गए संदेश",
    "track.nocall": "हमें कॉल करने की ज़रूरत नहीं। यह पेज अपने आप अपडेट होता है।", "track.done": "पूरा हुआ",
    "stage.quote": "प्लान स्वीकार", "stage.kyc": "दस्तावेज़ सत्यापित", "stage.sign": "अनुबंध पर हस्ताक्षर",
    "stage.install_sched": "इंस्टॉलेशन तय", "stage.installing": "इंस्टॉलेशन जारी", "stage.active": "सेवा चालू",
    "err.generic": "कुछ गड़बड़ हो गई। कृपया दोबारा कोशिश करें।",
    "explain.template": "आपके {business} ({staff} लोग, {city}) के लिए यह प्लान {items} को एक मासिक कीमत ₹{total} में देता है।",
}

# Keys the translator must not touch (language-neutral or brand).
NO_TRANSLATE = {"app.title", "kyc.gstin"}
_translating: set[str] = set()


def _cache_path(lang: str):
    return I18N_CACHE_DIR / f"{lang}.json"


def _load_cache(lang: str) -> dict:
    try:
        return json.loads(_cache_path(lang).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _placeholders(s: str) -> set[str]:
    return set(re.findall(r"\{\w+\}", s))


def translate_language(lang: str, chunk: int = 14) -> dict:
    """Translate EN -> lang with the local model, keep only strings whose placeholders survived."""
    out = dict(_load_cache(lang))
    todo = [k for k in EN if k not in out and k not in NO_TRANSLATE]
    for i in range(0, len(todo), chunk):
        keys = todo[i:i + chunk]
        res = translate_strings(lang, {k: EN[k] for k in keys})
        if not res:
            continue
        for k in keys:
            v = res.get(k)
            if isinstance(v, str) and v.strip() and _placeholders(v) == _placeholders(EN[k]):
                out[k] = v.strip()
        _cache_path(lang).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def get_dict(lang: str) -> dict:
    if lang == "en" or lang not in LANG_NAMES:
        return dict(EN)
    if lang == "hi":
        return {**EN, **HI}
    return {**EN, **_load_cache(lang)}


def translation_coverage(lang: str) -> float:
    if lang == "en":
        return 1.0
    have = HI if lang == "hi" else _load_cache(lang)
    keys = [k for k in EN if k not in NO_TRANSLATE]
    return len([k for k in keys if k in have]) / len(keys)


def ensure_translation_async(lang: str) -> None:
    """If a language has no cache yet, translate it in the background (next fetch will have it)."""
    if lang in ("en", "hi") or lang not in LANG_NAMES or lang in _translating:
        return
    if translation_coverage(lang) > 0.9 or not available():
        return
    _translating.add(lang)

    def run():
        try:
            translate_language(lang)
        finally:
            _translating.discard(lang)

    threading.Thread(target=run, daemon=True).start()


def t(lang: str, key: str, **params) -> str:
    s = get_dict(lang).get(key) or EN.get(key, key)
    try:
        return s.format(**params)
    except (KeyError, IndexError):
        return s
