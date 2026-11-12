# Galaxy Watch3 (SM-R845U) — standalone Verizon eSIM: SOLVED

## Root cause that blocked it for so long
The Galaxy Wearable plugin matches the **phone SIM's operator** against Samsung's SGC config
(`lookup.esimsamsung.com/v1/operators/subscriptionInfo?mcc=..&mnc=..`) and checks the watch
model against that operator's `approved_versions`.

- Visible eSIM (311/480, GID1 BAE1000000000000) -> operator entry "Visible"
  -> approved_versions lacks SM-R845U -> `supportedGear = -5`
  -> `WATCH_NOT_SUPPORTED_IN_THE_REGION`
- T-Mobile family (310/240) -> entry "TMobile" -> SM-R845U present -> `supportedGear = 0`
  but QrSupport = false, so no code entry.
- **Verizon (311/480, real Verizon eSIM)** -> entry "Verizon" -> SM-R845U present AND
  **QrSupport = true** -> app offers "Use code".

Approved version object for Verizon:
{"TMB":"R845USQU0ATD8","XAR":"R845USQU0ATD8","ATT":"R845USQU0ATD8",
 "VZW":"R845USQU0ATD8","SPR":"R845USQU0ATD8","USC":"R845USQU0ATD8"}

## Working procedure
1. Put a **real Verizon eSIM** in the phone that runs Galaxy Wearable
   (a free Verizon trial eSIM works; Visible is NOT Verizon).
2. Pair the watch and continue through setup to **Set up a mobile plan**.
3. The screen now reads:
   "If you have a QR code or activation code, tap Use code."
   (Because Verizon's entry has QrSupport=true.)
4. Tap **Use code** -> QR scanner (CaptureActivity) -> "Enter an activation code instead".
5. Get the eSIM activation code from Verizon for the watch line:
   `LPA:1$2.vzw.otgeuicc.com$<matching-id>`  (or the QR image).
   - My Verizon -> watch line -> Activate / Switch device -> eSIM activation
   - or call 611 and ask for the eSIM activation code / QR for the Galaxy Watch3 line.
6. Submit. Log shows:
   `handleProfileDownloadRes() - result : success`
   `sendModifyProfileRequest() - modifyType : enable`
   `profileList : [{ ProfileName: Verizon, Mcc: 311, Mnc: 480, Enabled: true }]`
   `profileCount : 1`
7. Done. Dashboard shows "Mobile data, Verizon".

## Verification
Turn Wi-Fi and Bluetooth off on the watch; it registers on LTE (rmnet interface,
own phone number).

## Notes / cautions
- The watch eSIM is independent of the phone. Removing the phone's Verizon trial eSIM
  does not remove the watch line.
- Do NOT factory reset the watch casually - a reset can remove the eSIM profile.
- The watch was reset during this work: TIDAL / WhatsApp setup must be redone.
  TIDAL .wgt: TIDAL-1.1.0.wgt
  companion APK: companion-patched-signed.apk
- Local sdb access: watchsdb.py + wsh.py (this repo, key ~/.tizen-sdb-key.pem).
  Note: the watch's sdbd wedges after some sessions; a full power cycle clears it.
