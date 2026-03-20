import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type Lang = 'zh' | 'en'

// 全量翻译表
const messages = {
  zh: {
    // 通用
    appName: 'AIMV Studio',
    loading: '加载中...',
    save: '保存',
    cancel: '取消',
    confirm: '确认',
    delete: '删除',
    edit: '编辑',
    back: '返回',
    prev: '上一页',
    next: '下一页',
    total: '共',
    page: '页',

    // 导航
    navHome: '首页',
    navGallery: '作品广场',
    navProjects: '我的项目',
    navCreate: '创作',
    navLogin: '登录',
    navLogout: '退出',

    // 状态标签
    statusDraft: '草稿',
    statusPlanning: '规划中',
    statusGenerating: '生成中',
    statusDone: '已完成',
    statusFailed: '失败',
    statusPending: '等待',
    statusRunning: '运行中',
    statusCompleted: '已完成',

    // 登录/注册
    loginTitle: '欢迎回来',
    registerTitle: '创建账号',
    loginSubtitle: '登录以继续',
    registerSubtitle: '加入 AI MV 创作革命',
    username: '用户名',
    email: '邮箱',
    password: '密码',
    loginBtn: '登录',
    registerBtn: '注册',
    toRegister: '没有账号？',
    toLogin: '已有账号？',
    loginError: '登录失败，请重试',

    // 项目列表
    myProjects: '我的项目',
    newProject: '+ 新建项目',
    noProjects: '还没有项目，创建你的第一个 MV 吧！',
    projectUntitled: '未命名 MV',

    // 创作页
    aiDirector: 'AI 导演',
    uploadAudio: '上传音频',
    chatPlaceholder: '描述你想创作的 MV 风格、情绪、故事...',
    send: '发送',
    thinking: '思考中...',
    generatePlan: '生成方案',
    generating: '规划中...',
    startGenerating: '开始生成',
    generatingMV: '生成中...',
    abCompare: 'A/B 对比',
    export: '导出',
    mvPreview: 'MV 预览',
    previewPlaceholder: '生成的内容将在这里显示',
    properties: '参数设置',
    visualStyle: '视觉风格',
    videoModel: '视频模型',
    musicModel: '音乐模型',
    mood: '情绪',
    generationStatus: '生成状态',
    storyboard: '分镜方案',
    autoRouted: '自动选择',
    readyToPlan: '信息已充足！点击「生成方案」创建分镜。',
    audioAnalyzed: '音频分析完成！',
    generationComplete: 'MV 生成完成！',
    startSuccess: '生成已启动，请在右侧面板查看进度',
    planFirst: '请先生成创作方案！',
    progressLost: '进度连接断开，正在重连...',

    // 风格选项
    styleKpop: 'K-Pop 韩娱',
    styleChinese: '国风古典',
    styleCyberpunk: '赛博朋克',
    styleRetro: '复古迪斯科',
    styleIndie: '独立电影',
    styleUrban: '都市甜酷',
    styleFantasy: '幻想童话',

    // 情绪选项
    moodEnergetic: '活力澎湃',
    moodMelancholic: '忧郁伤感',
    moodRomantic: '浪漫唯美',
    moodEpic: '史诗宏大',
    moodPeaceful: '平静舒缓',

    // 分镜标签
    labelSing: '演唱',
    labelStory: '叙事',
    segment: '片段',

    // 编辑器
    editorTitle: '导出编辑器',
    backToStudio: '返回创作室',
    mediaLibrary: '媒体库',
    images: '图片',
    videoClips: '视频片段',
    audio: '音频',
    noFinalVideo: '暂无最终视频',
    exportMV: '导出 MV',
    exportPlatform: '选择平台',
    burnSubtitles: '烧录字幕（歌词）',
    addWatermark: '添加水印',
    watermarkText: '水印文字',
    exportBtn: '开始导出',
    exporting: '导出中...',
    exportReady: '导出完成！',
    exportFailed: '导出失败',
    exportStarted: '导出已启动，完成后将通知您',

    // 错误消息
    chatError: '出现错误，请重试',
    generatePlanError: '生成方案失败，请重试',
    startGenerateError: '启动生成失败，请重试',
    uploadAudioError: '音频上传失败',
    connectionLost: '连接中断，正在重连...',

    // 画廊
    galleryTitle: '作品广场',
    allStyles: '全部',
    noWorks: '还没有发布的作品，来第一个分享吧！',
    likes: '点赞',

    // 平台导出
    platformDouyin: '抖音 9:16',
    platformBilibili: '哔哩哔哩 16:9',
    platformYoutube: 'YouTube 16:9 HQ',
    platformXhs: '小红书 3:4',
    platformInstagram: 'Instagram Reels',
    platformOriginal: '原始画质',
  },
  en: {
    appName: 'AIMV Studio',
    loading: 'Loading...',
    save: 'Save',
    cancel: 'Cancel',
    confirm: 'Confirm',
    delete: 'Delete',
    edit: 'Edit',
    back: 'Back',
    prev: 'Prev',
    next: 'Next',
    total: 'Total',
    page: 'Page',

    navHome: 'Home',
    navGallery: 'Gallery',
    navProjects: 'My Projects',
    navCreate: 'Create',
    navLogin: 'Login',
    navLogout: 'Logout',

    statusDraft: 'Draft',
    statusPlanning: 'Planning',
    statusGenerating: 'Generating',
    statusDone: 'Done',
    statusFailed: 'Failed',
    statusPending: 'Pending',
    statusRunning: 'Running',
    statusCompleted: 'Completed',

    loginTitle: 'Welcome Back',
    registerTitle: 'Create Account',
    loginSubtitle: 'Sign in to continue',
    registerSubtitle: 'Join the AI MV revolution',
    username: 'Username',
    email: 'Email',
    password: 'Password',
    loginBtn: 'Sign In',
    registerBtn: 'Register',
    toRegister: "Don't have an account?",
    toLogin: 'Already have an account?',
    loginError: 'Login failed, please try again',

    myProjects: 'My Projects',
    newProject: '+ New Project',
    noProjects: 'No projects yet. Create your first MV!',
    projectUntitled: 'Untitled MV',

    aiDirector: 'AI Director',
    uploadAudio: 'Upload Audio',
    chatPlaceholder: 'Describe your MV idea — style, mood, story...',
    send: 'Send',
    thinking: 'Thinking...',
    generatePlan: 'Generate Plan',
    generating: 'Planning...',
    startGenerating: 'Start Generating',
    generatingMV: 'Generating...',
    abCompare: 'A/B Compare',
    export: 'Export',
    mvPreview: 'MV Preview',
    previewPlaceholder: 'Generated content will appear here',
    properties: 'Properties',
    visualStyle: 'Visual Style',
    videoModel: 'Video Model',
    musicModel: 'Music Model',
    mood: 'Mood',
    generationStatus: 'Generation Status',
    storyboard: 'Storyboard',
    autoRouted: 'Auto (AI Routed)',
    readyToPlan: 'Enough info gathered! Click "Generate Plan" to create your storyboard.',
    audioAnalyzed: 'Audio analyzed!',
    generationComplete: 'MV generation completed!',
    startSuccess: 'Generation started! Watch progress on the right panel.',
    planFirst: 'Generate a plan first!',
    progressLost: 'Progress connection lost, reconnecting...',

    styleKpop: 'K-Pop',
    styleChinese: 'Chinese Classical',
    styleCyberpunk: 'Cyberpunk',
    styleRetro: 'Retro Disco',
    styleIndie: 'Indie Film',
    styleUrban: 'Urban Cool',
    styleFantasy: 'Fantasy',

    moodEnergetic: 'Energetic',
    moodMelancholic: 'Melancholic',
    moodRomantic: 'Romantic',
    moodEpic: 'Epic',
    moodPeaceful: 'Peaceful',

    labelSing: 'Sing',
    labelStory: 'Story',
    segment: 'Segment',

    editorTitle: 'Export Editor',
    backToStudio: 'Back to Studio',
    mediaLibrary: 'Media Library',
    images: 'Images',
    videoClips: 'Video Clips',
    audio: 'Audio',
    noFinalVideo: 'No final video yet',
    exportMV: 'Export MV',
    exportPlatform: 'Select Platform',
    burnSubtitles: 'Burn subtitles (lyrics)',
    addWatermark: 'Add watermark',
    watermarkText: 'Watermark text',
    exportBtn: 'Export',
    exporting: 'Exporting...',
    exportReady: 'Export ready!',
    exportFailed: 'Export failed',
    exportStarted: 'Export started. You will be notified when ready.',

    // Error messages
    chatError: 'An error occurred, please try again',
    generatePlanError: 'Failed to generate plan, please try again',
    startGenerateError: 'Failed to start generation, please try again',
    uploadAudioError: 'Audio upload failed',
    connectionLost: 'Connection lost, reconnecting...',

    galleryTitle: 'Gallery',
    allStyles: 'All',
    noWorks: 'No published works yet. Be the first to share!',
    likes: 'Likes',

    platformDouyin: 'Douyin 9:16',
    platformBilibili: 'Bilibili 16:9',
    platformYoutube: 'YouTube 16:9 HQ',
    platformXhs: 'Xiaohongshu 3:4',
    platformInstagram: 'Instagram Reels',
    platformOriginal: 'Original',
  },
} as const

type Messages = typeof messages.zh

export const useLangStore = defineStore('lang', () => {
  const lang = ref<Lang>((localStorage.getItem('aimv_lang') as Lang) || 'zh')

  function setLang(l: Lang) {
    lang.value = l
    localStorage.setItem('aimv_lang', l)
  }

  const t = computed(() => (key: keyof Messages): string => {
    return (messages[lang.value] as Messages)[key] ?? (messages.en as Messages)[key] ?? key
  })

  return { lang, setLang, t }
})
