# Getting the two free logo keys (for Jack)

Both keys are free and are the kind that is **meant to be seen** in a web page's code, so pasting them into the
Claude chat is fine. Never copy any key called "secret" (logo.dev's starts with `sk_`): we don't need it, and the test
refuses it. No credit card is needed for either.

I could not open the two sign-up pages from the cloud computer (both block automated visitors), so the button names
below come from the providers' own help pages and may be worded slightly differently on screen.

## 1. Brandfetch — "client ID" (about 3 minutes)

1. On your computer or phone, open **https://developers.brandfetch.com/register**.
2. Create a free account (email and password, or a sign-in button if offered). If it asks what you are building,
   something like "free educational stock research site, company logos next to stock names" is accurate.
3. Confirm your email if it sends you a link.
4. You land on the **Developer Portal dashboard** (developers.brandfetch.com). Your **client ID** is shown there — a
   string of letters and digits. If you see a choice of products, the one we use is the **Logo API** (it is free).
5. Copy the client ID and paste it into the Claude chat, labelled "Brandfetch client ID".

If the dashboard offers an **API key** for the "Brand API": don't copy that one. We only need the client ID.

## 2. logo.dev — "publishable key" (about 3 minutes)

1. Open **https://www.logo.dev/signup** and create a free account (no credit card). If it asks for a plan, pick the
   free one (called **Community**).
2. Open **https://www.logo.dev/dashboard/api-keys** (or Dashboard → **API keys**).
3. You see two keys. Copy only the one that **starts with `pk_`** (the publishable key). Do not copy the one that
   starts with `sk_` (secret key).
4. Leave **"Allowed domains only"** switched **off** for now (the test runs from a test page; we switch it on later
   with jacksungjinlee.github.io when logos go into the app).
5. Paste the `pk_…` key into the Claude chat, labelled "logo.dev publishable key".

## What Claude does with them

- Keeps them only in a private file in the session's scratch folder (outside the code), loads them as
  `BRANDFETCH_CLIENT_ID` and `LOGODEV_TOKEN`, and never prints them, commits them or writes them into results
  (every log line shows `***` instead).
- Runs a small pilot first (the 200 largest Korean and 200 largest US companies, about 6 minutes), shows you the
  picture of those logos, then the full test (about an hour), and deletes the key file afterwards.

## One question for you (logo.dev only)

logo.dev's free plan asks **commercial** projects to show a small link "Logos provided by Logo.dev". By their rules a
project you own as an individual that earns nothing is **personal** and needs no link. 뱁새 is free and has no ads, so
it counts as personal today. If it ever earns money (ads, paid features) or a company owns it, the link becomes
required. Brandfetch asks for no link either way.
