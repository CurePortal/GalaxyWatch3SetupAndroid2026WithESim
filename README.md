# Galaxy Watch3 (SM-R845U) on a non-Samsung Android phone — pairing + standalone Verizon eSIM

**Status: SOLVED and verified** on a US-unlocked Galaxy Watch3 (SM-R845U, CSC `XAR`,
build `R845USQU1DWK2`, Tizen 5.5.0.2) paired to a **Motorola** phone, with a working
**standalone Verizon LTE eSIM and its own phone number**.

This guide has two parts:

1. **Pairing** a Samsung Tizen watch to a non-Samsung Android phone, including the
   "Finishing up…" setup deadlock that stops most people.
2. **Activating a standalone Verizon eSIM**, including why Galaxy Wearable says
   *"There aren't any mobile plans available for your watch in your country"* and how to
   get past it.

No root, no firmware flashing, no paid tools.

---

# Part 1 — Pairing the watch to a non-Samsung phone

A Galaxy Watch3 pairs to any modern Android phone through **Galaxy Wearable**, but on a
non-Samsung phone it needs three APKs, not one, and the setup wizard has a known deadlock.

## 1.1 What you need

| APK | Package | Version used here |
|---|---|---|
| Galaxy Wearable | `com.samsung.android.app.watchmanager` | 2.2.72.26092361 |
| Watch3 plugin | `com.samsung.android.gearnplugin` | 2.2.09.24012551 |
| Accessory Service | `com.samsung.accessory` | 3.1.96.61123 |

You do **not** need a Samsung account to pair. You only need one for Galaxy Store
content. The Play Store sometimes refuses to offer Galaxy Wearable on non-Samsung phones
in some regions — sideload the APKs instead (`adb install -r <apk>` or tap them on the
phone with "install unknown apps" allowed).

**Install order matters:** Accessory Service → Galaxy Wearable → Watch3 plugin.

```bash
adb install -r accessory-service.apk
adb install -r galaxy-wearable.apk
adb install -r watch3-plugin.apk
```

## 1.2 Prepare the watch

- Charge it above ~30%. Setup refuses to finish on very low battery.
- If it was paired to another phone before, **reset it first**:
  *Settings → General → Reset → Reset*. (Or unpair it from the old phone's Galaxy
  Wearable, which resets it.)
- If the watch shows a **Reactivation Lock** / previous owner's Samsung account, stop:
  only the previous owner can remove it (they must sign in and remove the device, or
  reset it from their Samsung account).
- Turn the watch on and leave it on the "Welcome / language" screen.

## 1.3 Pair

1. On the phone, open **Galaxy Wearable → Add device / Scan**.
2. Choose the watch from the list (keep it close, Bluetooth on).
3. Both devices show a **pairing code** — confirm on the watch and the phone.
4. The watch begins "Copying your apps" / setup.

Grant whatever the phone asks for: **Nearby devices**, **Location**, and — important for
later — **Notification access** for the watch plugin (`com.samsung.android.gearnplugin`'s
`NotificationListener`). Without it, phone notifications never reach the watch.

## 1.4 The "Finishing up…" deadlock (the big one)

On non-Samsung phones the OOBE commonly freezes here:

```
Finishing up…
This might take a few minutes.
While you're waiting, take a moment to get familiar with your watch.
```

It never finishes. This is not a pairing failure — the Samsung OOBE broadcast it waits for
is never sent. Fix it with adb while the phone is connected over USB with **USB debugging**
enabled (Developer options → USB debugging):

```bash
adb shell am broadcast -a OOBE_FLOW_CONTINUE_REQUEST
```

Within a few seconds the phone continues to the **Samsung Terms** screen:

- **For your review** — tap **Continue**
- **Terms / diagnostics** — the optional toggles can stay off

Then the wizard moves on to the mobile-plan step (see Part 2) and finally the watch
dashboard.

> If you don't have adb, you can also force it by restarting Galaxy Wearable, but the
> broadcast is instant and reliable.

## 1.5 Finish setup

- If it asks to **install Samsung Health**, tap **Not now** — it isn't needed and doesn't
  work properly on non-Samsung phones.
- Wait for the **Galaxy Watch3** dashboard with battery %, Watch faces, Apps, Widgets,
  Quick panel, Watch settings.
- Pairing is complete.

## 1.6 Verify the pairing is healthy

On the phone:

```bash
adb shell dumpsys activity activities | grep -m1 topResumedActivity
# com.samsung.android.gearnplugin/com.samsung.android.gearoplugin.maininfo.MainInfoActivity
```

On the watch: swipe down for the Quick panel; the Bluetooth icon should be solid, and
Galaxy Wearable should show a battery percentage and "Connected".

## 1.7 Optional: developer access on the watch (for logs / sdb)

- Watch: *Settings → About watch → Software → tap "Software version" 5×*
- Then *Settings → Developer options → Debugging = ON*
- Connect the watch to the same Wi-Fi as your computer to use `sdb connect <ip>:26101`

---

# Part 2 — Standalone Verizon eSIM

## TL;DR

1. The blocker is **not** Verizon, the EID/IMEI, or the phone. It is Samsung's
   per-operator carrier config, which only lists `SM-R845U` for *some* operators.
2. **Visible / Visible eSIM does not work** — its MVNO entry omits the Watch3.
3. **T-Mobile works for the gate but has no QR support**, and the watch isn't registered.
4. **A real Verizon eSIM (a free trial eSIM is enough) is the key.** Verizon's entry
   *does* list `SM-R845U` **and** has `QrSupport = true`, which makes Galaxy Wearable show
   **"Use code"**.
5. Enter the watch line's activation code:
   `LPA:1$2.vzw.otgeuicc.com$<matching-id>`.

## 2.1 The error everyone hits

Galaxy Wearable → Watch settings → Mobile plans:

> **"There aren't any mobile plans available for your watch in your country."**
> *Contact Samsung Customer Service for more information.*

Only a **Skip** button. The plugin log says:

```
[ESIM]_ : MobileNetworksInfo.setMobileNetworksInfo() - mESSupport : true, onlineSupport : true,
          mQRSupport : true, mOfflineSupport : false, mExtendedAuthSupport : true,
          mCallForkingStatusFromSGC : false, mSupportedGear : -5
[ESIM]_ : SetupWizardMobileNetworkSetupActivity.getSupportedGear() - -5
[ESIM]_ : showMobileNetworkError() > exceptionCode : WATCH_NOT_SUPPORTED_IN_THE_REGION
```

`-5` → `WATCH_NOT_SUPPORTED_IN_THE_REGION`. The message is misleading: it is not about the
country, it is about the **operator entry** Samsung returned for your phone's SIM.

## 2.2 Root cause

The plugin has the watch fetch Samsung's SGC operator list:

```
https://lookup.esimsamsung.com/v1/operators/subscriptionInfo?mcc=<MCC>&mnc=<MNC>
```

The phone matches one entry using the **phone SIM's GID1/IMSI**, then validates the watch
model against that entry's `approved_versions`:

```
JSONObject approved = gmFeature.getJSONObject("approved_versions");
JSONObject versions = approved.getJSONObject("SM-R845U");   // throws if absent
```

If `SM-R845U` is not a key → `supportedGear = -5` → the app refuses.

Captured from a real Watch3:

| Phone SIM | Matched entry | `SM-R845U` in entry? | QR support |
|---|---|---|---|
| Visible (311/480, GID1 `BAE1000000000000`) | `Visible` | **no** → `-5` | — |
| TruConnect / T-Mobile family (310/240) | `TMobile` | yes → `0` | **false** |
| **Verizon (311/480)** | `Verizon` | yes → `0` | **true** |

Verizon's entry returned:

```
Result : SUCCESS, ResultCode : 1000
EsSupport : true, OnlineSupport : true, QrSupport : true
SmdpAddress : [https://www.verizon.com]
OperatorName : Verizon
approvedVersionObject :
  {"TMB":"R845USQU0ATD8","XAR":"R845USQU0ATD8","ATT":"R845USQU0ATD8",
   "VZW":"R845USQU0ATD8","SPR":"R845USQU0ATD8","USC":"R845USQU0ATD8"}
supportedGear : 0
```

Because `QrSupport = true`, the app stops saying "no plans" and shows:

> **"Mobile service for your watch"**
> *If you have a QR code or activation code, tap **Use code**.*

That is the entire secret.

## 2.3 Prerequisites

- Galaxy Watch3 LTE **SM-R845U** (model-specific)
- The watch already paired (Part 1)
- **A Verizon eSIM in that phone** — the free Verizon trial eSIM is sufficient. It does
  not need to be the watch's plan; it only supplies the operator identity.
- The watch line's **activation code**: `LPA:1$2.vzw.otgeuicc.com$<matching-id>`
  (or the QR image)

## 2.4 Procedure

### Step 1 — Put a Verizon eSIM in the phone

Confirm the phone reports it:

```bash
adb shell getprop gsm.sim.operator.alpha     # -> Verizon
adb shell getprop gsm.sim.operator.numeric   # -> 311480
```

If there is a second SIM (physical or eSIM), make sure the **Verizon one is selected**
when the plugin asks which SIM to use.

### Step 2 — Open the mobile-plan step

Galaxy Wearable → **Watch settings → Mobile plans** (or continue the setup wizard).

With the Verizon eSIM you should see the data-consent screen and then:

```
Mobile service for your watch
If you have a QR code or activation code, tap Use code.
[ Use code ]   Don't have a plan? Sign up for one now   Skip | Next
```

Still seeing *"There aren't any mobile plans available…"*? The phone didn't match
Verizon's entry — re-check the active SIM.

### Step 3 — Get the activation code from Verizon

- **My Verizon** → the watch line → *Activate / Switch device* → **eSIM activation**
  (shows a QR and an `LPA:` code)
- or call **611** and ask for the *eSIM activation code / QR for the Galaxy Watch3 line*

Format:

```
LPA:1$2.vzw.otgeuicc.com$ABC123DEF456
```

> Entering only `https://2.vzw.otgeuicc.com` gives **"QR code not valid"** — the matching
> ID is required.

### Step 4 — Enter it

Tap **Use code** → the QR scanner opens.

Scan the QR, or tap **"Enter an activation code instead"** and paste the `LPA:1$…$…`
string.

The watch downloads and enables the profile. The phone log shows:

```
[ESIM]_ : HMeSIMManager.handleProfileInstallProgressRNoti() - progress : 99
[ESIM]_ : ESimJSONReceiver.handleProfileDownloadRes() - result : success, reason : 0,
          profileId : ****************
[ESIM]_ : SetupWizardMobileNetworkHandler.handleProfileDownloadedResponse() - result : success
[ESIM]_ : eSIMUtil.sendModifyProfileRequest() - modifyType : enable
[ESIM]_ : HMeSIMManagerInternal.handleModifyProfile() - type : enable / success : true
[ESIM]_ : ProfileManager.getList() - profileList :
          [{ ProfileId : ****************, ProfileName : Verizon, CarrierName : Verizon,
             DisplayName : Verizon-XXXX, Mcc : 311, Mnc : 480, Enabled : true }]
[ESIM]_ : eSIMUtil.getESIMProfileCount() - profileCount : 1
```

Tap **Done**. The dashboard shows **"Mobile data, Verizon"**.

## 2.5 Verification

1. Turn **Wi-Fi off** and **Bluetooth off** on the watch.
2. It registers on LTE (`/proc/net/dev` shows an `rmnet*` interface carrying data).
3. Call the watch's own number — it rings on the watch.
4. Texts and data work without the phone.

## 2.6 Bluetooth vs LTE — one or the other (by design)

Samsung's Tizen watches **park the cellular radio while connected to the phone via
Bluetooth or Wi-Fi remote connection**, to save battery. Samsung's own team confirms:

> *"Cellular is actually switched off when you are in Bluetooth range… It won't use your
> Cellular while within Bluetooth range — if it didn't your watch would run out of battery
> much quicker."*

| State | What works |
|---|---|
| Bluetooth connected | Notifications, calls via the **phone's** number. Calls to the watch's own number go to voicemail. |
| Bluetooth off / out of range | The watch's **own** number works on LTE (calls, texts, data). |

There is **no Tizen 5.5 setting** that keeps the watch's own line live for voice while
Bluetooth is connected. "Mobile data → Always on" keeps data alive, not voice.

For a single number that rings whether the watch is near the phone or not, use
**Verizon NumberShare** (watch shares the phone's number) — it needs a Verizon postpaid
phone line. A standalone watch line intentionally behaves as two separate states.

## 2.7 Troubleshooting

**"There aren't any mobile plans available for your watch in your country."**
Wrong operator entry for the phone SIM. Check:
`adb shell getprop gsm.sim.operator.numeric`.
Visible/MVNO → fails. T-Mobile family → gate opens, no QR. Verizon → works.

**"QR code not valid"**
Only an SM-DP+ URL was entered. Use the full code with the matching ID.

**"WATCH_NOT_SUPPORTED_IN_THE_REGION" / `supportedGear: -5`**
Same as above.

**"Sign up for one now" but no "Use code"**
That operator has `QrSupport = false`. Only Verizon (of those tested) exposes code entry
for this watch.

**Profile downloads but calls don't arrive with Bluetooth on**
Expected — see 2.6.

**After a factory reset the eSIM is gone**
A reset can remove the profile. Avoid resetting once the eSIM is installed.

## 2.8 What does NOT work (tested)

- **Sideloading an eSIM profile as a package.** Profiles are issued by the carrier's
  SM-DP+ for a specific EID; they are not `.wgt`/`.tpk` files.
- **Visible / Visible eSIM.** Its Samsung operator entry only approves Watch4-era models.
- **T-Mobile / Metro.** Gate opens (`supportedGear = 0`) but `QrSupport = false`, the
  watch isn't registered, and entitlement returns no subscription URL.
- **The watch's standalone "country → provider" list.** On this watch (XAR, Nov 2026) it
  lists only T-Mobile and Metro for the USA. Verizon never appears there.
- **`sdb root on`.** Retail Tizen 5.5 returns `Permission denied`; no `rootsh`/`su`,
  `sdbd` is not setuid. Root only exists under Samsung combination firmware.
- **Calling the eSIM D-Bus API directly.** `/org/tizen/esim`,
  `org.tizen.esim.Manager` (`DownloadProfile`, `EnableProfile`, `GetEid`, …) is protected
  by `/etc/dbus-1/system.d/esim-server.conf`, which requires the privilege
  `http://developer.samsung.com/tizen/privilege/esim`. Only Samsung apps hold it; the
  shell user is explicitly denied and `security-manager-cmd` reports insufficient rights.
- **DNS spoofing the lookup.** The SGC HTTPS call is made by the **watch**, not the phone,
  and is mutually authenticated (the server requests a client certificate). Spoofing needs
  a CA installed on the watch — i.e. root.

---

# Appendix A — technical detail

### Operator matching (plugin)

```
SgcManager.getMatchedOperator():
  filter entries whose targetModels includes the watch model (SM-R845U)
  match by SIM GID1 / IMSI subset
  fallback: most frequent entry with empty gid1
```

### Model validation (plugin)

```
HMeSIMManagerInternal.isSupportedGear():
  if gmFeature is empty -> 0
  approved = gmFeature.approved_versions
  versions = approved[MODEL]            // throws -> -5
  salesCode = BNR_DEVICEINFO/SALES_CODE // e.g. XAR
  if versions has salesCode -> compare last 4 chars of SOFTWARE_VERSION
  else if "ALL" key -> compare
  else -> -1
```

### Log filters

```bash
adb logcat | grep -E "\[ESIM\]" | grep -iE \
  "matched operatorInfo|setMobileNetworksInfo|supportedGear|approvedVersion|exceptionCode|resultCode|ProfileDownload|profileList"

adb logcat | grep -E "Finishing|OOBE|SetupWizardComplete"
```

### Driving the UI from adb (optional)

`uiautomator dump` + `input tap` works on the eSIM dialogs. The QR/code entry screen is
`com.samsung.android.gearoplugin.esim.android.CaptureActivity` (not exported, but reached
through "Use code"); manual entry is a fragment inside `HMSecondFragmentActivity`.

### Watch shell (sdb over Wi-Fi)

Tizen sdb uses a packet protocol similar to adb. `watchsdb.py` / `wsh.py` in this repo are
a minimal Python client (useful when Samsung's `sdb` binary is blocked by macOS Local
Network permissions). Notes:

- The watch accepts one sdb host; the first connection shows an "allow" prompt.
- The daemon can wedge (TCP connects, no handshake). A full **power cycle** clears it.
- `sdb root on` → `Permission denied` on retail firmware.

### Files of interest on the watch

```
/csa/csc/csc-active-customer.inf              -> active CSC (XAR)
/opt/system/csc-default/SW_Configuration.xml  -> multi-CSC package R845UOYN
                                                 customers: XAR ATT SPR TMB USC VZW
/opt/data/esimmgr/eSIMManagerConfig.xml       -> profileMaxNumber: 2
/opt/data/esimmgr/local_certificate/          -> carrier TLS certificates
```

The stock firmware is a multi-CSC package that already contains `/Customer/VZW/`, so the
hardware and firmware are Verizon-capable. Only the server-side operator gate stood in
the way.

---

# Appendix B — quick reference

```bash
# Pairing deadlock
adb shell am broadcast -a OOBE_FLOW_CONTINUE_REQUEST

# Confirm the phone SIM drives the eSIM gate
adb shell getprop gsm.sim.operator.alpha      # Verizon
adb shell getprop gsm.sim.operator.numeric    # 311480

# Watch shell over Wi-Fi (after enabling Debugging)
sdb connect <watch-ip>:26101
```

Activation code:

```
LPA:1$2.vzw.otgeuicc.com$<matching-id>
```

---

## Credits

Worked out by inspecting the Galaxy Wearable plugin (`com.samsung.android.gearnplugin`
2.2.09.24012551) and the Watch3's own eSIM stack, with live logs from a retail SM-R845U
paired to a Motorola phone.

Licence: CC BY 4.0 — copy, adapt, repost.
