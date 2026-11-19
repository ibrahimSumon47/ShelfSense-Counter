// Natural English ('en') and Bangla ('bn') UI dictionaries for the ShelfSense operations dashboard.
// Written in clear retail operations phrasing (never word-for-word machine translation).

import { type ChatLocale } from './chat-tools.ts';

export interface Dictionary {
  appName: string;
  tagline: string;
  navScan: string;
  navHistory: string;
  navChat: string;
  themeDark: string;
  themeLight: string;
  langToggle: string;
  roleOwner: string;
  roleStaff: string;
  storeLabel: string;
  aisleLabel: string;
  shelfLabel: string;
  thresholdLabel: string;
  thresholdStaffHint: string;
  uploadPrompt: string;
  uploadSubtext: string;
  sampleButton: string;
  countTitle: string;
  gapsTitle: string;
  missingEstTitle: string;
  statusTitle: string;
  statusLowStock: string;
  statusHealthy: string;
  saveScanButton: string;
  exportCsvButton: string;
  historyHeading: string;
  historyEmpty: string;
  trendHeading: string;
  chatHeading: string;
  chatPlaceholder: string;
  chatSend: string;
  chatHint: string;
  errorInvalidFile: string;
  analysingTitle: string;
  analysingBody: string;
  errorModelLoad: string;
  overlayLabel: string;
  modelMissingTitle: string;
  modelMissingBody: string;
  noScanYet: string;
}

export const DICTIONARIES: Record<ChatLocale, Dictionary> = {
  en: {
    appName: 'ShelfSense',
    tagline: 'Retail shelf inventory counter and stock-gap monitor',
    navScan: 'Shelf Scan',
    navHistory: 'Scan History & Trends',
    navChat: 'Inventory Q&A',
    themeDark: 'Dark slate',
    themeLight: 'Light',
    langToggle: 'বাংলা',
    roleOwner: 'Role: Store Owner (can edit thresholds)',
    roleStaff: 'Role: Aisle Staff (scan only)',
    storeLabel: 'Store',
    aisleLabel: 'Aisle',
    shelfLabel: 'Shelf',
    thresholdLabel: 'Low-stock alert threshold',
    thresholdStaffHint: 'Only the store owner can change alert thresholds.',
    uploadPrompt: 'Upload or capture a shelf photo',
    uploadSubtext: 'Processed directly in your browser (ONNX Runtime). Photos stay on this device.',
    sampleButton: 'Load sample grocery shelf',
    countTitle: 'Detected Products',
    gapsTitle: 'Empty Shelf Gaps',
    missingEstTitle: 'Estimated Missing Units',
    statusTitle: 'Shelf Status',
    statusLowStock: 'Low Stock Alert',
    statusHealthy: 'Stock Normal',
    saveScanButton: 'Save scan to history',
    exportCsvButton: 'Export CSV',
    historyHeading: 'Saved Shelf Scans',
    historyEmpty: 'No shelf scans recorded for this filter yet. Run a scan above to log inventory.',
    trendHeading: 'Stock Count Trend by Scan',
    chatHeading: 'Ask About Stored Scans (Database Tool Grounded)',
    chatPlaceholder: 'e.g., Which shelf is lowest today? or Compare this week with last week',
    chatSend: 'Ask',
    chatHint: 'Every number comes strictly from stored scan records. Missing data is never guessed.',
    errorInvalidFile: 'Please select a valid JPEG, PNG, or WebP shelf photo under 10 MB.',
    analysingTitle: 'Analysing the photo',
    analysingBody: 'Detecting products in this browser. Nothing is uploaded while this runs.',
    errorModelLoad: 'The detector could not be loaded in this browser, so this photo was not analysed.',
    overlayLabel: 'Detected products on this shelf photo',
    modelMissingTitle: 'Detector not published in this build',
    modelMissingBody:
      'Photo analysis needs the detector file that ships with a release; this deployment has none, so nothing is analysed and no boxes are shown.',
    noScanYet: 'No photo analysed yet.',
  },
  bn: {
    appName: 'শেলফসেন্স (ShelfSense)',
    tagline: 'তাকের পণ্য গণনা, খালি জায়গা শনাক্তকরণ এবং স্টক সতর্কতা ড্যাশবোর্ড',
    navScan: 'তাক স্ক্যান',
    navHistory: 'স্ক্যানের ইতিহাস ও প্রবণতা',
    navChat: 'স্টক প্রশ্নোত্তর',
    themeDark: 'ডার্ক থিম',
    themeLight: 'লাইট থিম',
    langToggle: 'English',
    roleOwner: 'ভূমিকা: স্টোর মালিক (সতর্কতা সীমা পরিবর্তনযোগ্য)',
    roleStaff: 'ভূমিকা: স্টোর কর্মী (শুধু স্ক্যান)',
    storeLabel: 'স্টোর',
    aisleLabel: 'আইল (সারি)',
    shelfLabel: 'তাক (শেলফ)',
    thresholdLabel: 'কম স্টকের সতর্কতা সীমা',
    thresholdStaffHint: 'শুধুমাত্র স্টোর মালিক সতর্কতা সীমা পরিবর্তন করতে পারবেন।',
    uploadPrompt: 'তাকের ছবি আপলোড করুন অথবা ক্যামেরায় তুলুন',
    uploadSubtext: 'শনাক্তকরণ সরাসরি আপনার ব্রাউজারে সম্পন্ন হয়। মূল ছবি ডিভাইসের বাইরে যায় না।',
    sampleButton: 'নমুনা তাকের ছবি দেখুন',
    countTitle: 'শনাক্তকৃত পণ্য',
    gapsTitle: 'খালি ফাঁকা স্থান',
    missingEstTitle: 'আনুমানিক ঘাটতি পণ্য',
    statusTitle: 'তাকের অবস্থা',
    statusLowStock: 'কম স্টক সতর্কতা',
    statusHealthy: 'পর্যাপ্ত স্টক',
    saveScanButton: 'স্ক্যান সংরক্ষণ করুন',
    exportCsvButton: 'CSV ডাউনলোড',
    historyHeading: 'সংরক্ষিত তাক স্ক্যানের তালিকা',
    historyEmpty: 'এই ফিল্টারে এখনো কোনো স্ক্যান সংরক্ষিত নেই। উপরে একটি তাক স্ক্যান করে যোগ করুন।',
    trendHeading: 'সময়ের সাথে পণ্যের সংখ্যার প্রবণতা',
    chatHeading: 'সংরক্ষিত স্ক্যান সম্পর্কে প্রশ্ন করুন',
    chatPlaceholder: 'যেমন: আজ কোন তাকে সবচেয়ে কম পণ্য আছে? বা গত সপ্তাহের সাথে তুলনা করুন',
    chatSend: 'জিজ্ঞাসা করুন',
    chatHint: 'প্রতিটি সংখ্যা সরাসরি ডাটাবেসের সংরক্ষিত স্ক্যান থেকে নেওয়া হয়; অনুমান করে কোনো সংখ্যা বলা হয় না।',
    errorInvalidFile: 'অনুগ্রহ করে ১০ মেগাবাইটের কম আকারের সঠিক JPEG, PNG বা WebP ছবি নির্বাচন করুন।',
    analysingTitle: 'ছবিটি বিশ্লেষণ করা হচ্ছে',
    analysingBody: 'পণ্য শনাক্ত হচ্ছে আপনার ব্রাউজারেই। এই সময়ে কোনো ছবি আপলোড হয় না।',
    errorModelLoad: 'এই ব্রাউজারে ডিটেক্টর চালু করা যায়নি, তাই ছবিটি বিশ্লেষণ করা হয়নি।',
    overlayLabel: 'এই শেলফ ছবিতে শনাক্ত করা পণ্য',
    modelMissingTitle: 'এই সংস্করণে ডিটেক্টর যুক্ত নেই',
    modelMissingBody: 'ছবি বিশ্লেষণের জন্য রিলিজের সাথে আসা ডিটেক্টর ফাইল দরকার; এখানে সেটি নেই, তাই কোনোকিছু বিশ্লেষণ বা বক্স দেখানো হচ্ছে না।',
    noScanYet: 'এখনো কোনো ছবি বিশ্লেষণ করা হয়নি।',
  },
};
