# 🔄 دليل التزامن التلقائي لمكتبة الكتب مع الهاتف الذكي (Syncthing)

يوفر هذا الدليل طريقة مجانية، آمنة ومباشرة لتزامن مجلد مكتبة الكتب `/home/abdallah/Documents/ReadEra` بين حاسوبك المكتبي (Linux) وتطبيق **ReadEra** على الهاتف الذكي (Android) دون الاستعانة بسحابات مدفوعة وبسرعة عالية عبر الشبكة المحلية (Wi-Fi).

---

## 🛠️ الخطوة 1: تثبيت Syncthing على حاسوبك (Linux)

قم بفتح الطرفية (Terminal) وتشغيل الأمر التالي لتثبيت وتفعيل Syncthing:

```bash
# تثبيت البرنامج
sudo apt update && sudo apt install -y syncthing

# تفعيل الخدمة لتبدأ تلقائياً مع تشغيل الجهاز
systemctl --user enable --now syncthing
```

* بعد التشغيل، يمكنك فتح لوحة تحكم Syncthing في المتصفح عبر الرابط: [http://localhost:8384](http://localhost:8384)

---

## 📱 الخطوة 2: تثبيت Syncthing على الهاتف الذكي

1. قم بتثبيت تطبيق **Syncthing-Fork** أو **Syncthing** من متجر [Google Play Store](https://play.google.com/store/apps/details?id=com.github.catfriend1.syncthingapp) أو F-Droid.
2. افتح التطبيق وامنحه صلاحية الوصول للملفات (Storage Permission).

---

## 🔗 الخطوة 3: ربط الجهازين (Pairing)

1. افتح صفحة [http://localhost:8384](http://localhost:8384) على الحاسوب، واضغط على **"Actions"** -> **"Show ID"** ليظهر لك رمز كيو آر (QR Code).
2. افتح تطبيق Syncthing على هاتفك، انتقل إلى تبويب **"Devices"** واضغط على زر الإضافة `+` ثم امسح الـ QR Code الخاص بحاسوبك.
3. ستظهر لك رسالة تأكيد في متصفح الحاسوب لإضافة الهاتف، اضغط **"Add Device"**.

---

## 📂 الخطوة 4: مشاركة مجلد المكتبة `ReadEra`

1. في لوحة تحكم الحاسوب [http://localhost:8384](http://localhost:8384)، اضغط على **"Add Folder"**:
   * **Folder Label:** `ReadEra Library`
   * **Folder Path:** `/home/abdallah/Documents/ReadEra`
2. انتقل إلى تبويب **"Sharing"** وحدد جهاز هاتفك المحمول.
3. اضغط **"Save"**.

---

## 📱 الخطوة 5: استقبال المجلد في الهاتف وتوجيهه لـ ReadEra

1. ستصلك إشعارة في تطبيق Syncthing على الهاتف تفيد برغبة الحاسوب في مشاركة مجلد `ReadEra Library`.
2. وافق على الرسالة واختر مسار الحفظ في هاتفك داخل مجلد `Documents/ReadEra` أو المجلد المعتاد لتطبيق ReadEra.
3. افتح تطبيق **ReadEra** على الهاتف، وسيقوم التطبيق فوراً بفحص الكتب الجديدة وتصنيفها بنفس الهيكلة الفرعية التي أنشأناها!

---

🎉 **تهانينا!** الآن، أي كتاب تضيفه أو تنظفه أو تعيد ترتيبه على جهاز الحاسوب سينتقل تلقائياً وبشكل فورياً إلى هاتفك الذكي!
