import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import zhCN from './locales/zh-CN.json'

// 从 localStorage 获取保存的语言偏好，默认为英文
function getStoredLocale() {
  try {
    return localStorage.getItem('pre-locale') || 'en'
  } catch {
    return 'en'
  }
}

const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: getStoredLocale(),
  fallbackLocale: 'en',
  messages: {
    en,
    'zh-CN': zhCN
  }
})

export default i18n

// 切换语言并保存到 localStorage
export function setLocale(locale) {
  i18n.global.locale.value = locale
  try {
    localStorage.setItem('pre-locale', locale)
  } catch {
    // localStorage 不可用时静默失败
  }
}

// 获取当前语言
export function getLocale() {
  return i18n.global.locale.value
}

// 获取可用语言列表
export function getAvailableLocales() {
  return [
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'zh-CN', name: '中文', flag: '🇨🇳' }
  ]
}
