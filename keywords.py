TARGET_KEYWORDS = {
    "healthtech": [
        "healthtech",
        "health tech",
        "digital health",
        "digital healthcare",
        "медицина",
        "медицин",
        "здравоохран",
        "healthcare",
    ],

    "medtech": [
        "medtech",
        "med tech",
        "медтех",
        "медицинское оборудование",
        "medical device",
    ],

    "femtech": [
        "femtech",
        "женское здоровье",
        "women's health",
        "women health",
        "fertility",
        "репродуктив",
        "гинеколог",
    ],

    "machine_learning": [
        "machine learning",
        "машинное обучение",
    ],

    "recsys": [
        "recommender system",
        "recommender systems",
        "recommendation system",
        "рекомендательн",
        "система рекомендаций",
    ],
}

ROLE_TAXONOMY = {
    "data_scientist": [
        "data scientist",
        "дата-сайентист",
        "дата саентист",
        "дата сайентист",
        "исследователь данных",
    ],

    "ml_engineer": [
        "ml engineer",
        "ml-инженер",
        "ml инженер",
        "machine learning engineer",
        "machine-learning engineer",
        "инженер машинного обучения",
        "мо-инженер",
        "мо инженер",
        "инженер мо",
    ],

    "ai_ml_engineer": [
        "ai/ml engineer",
        "ai/ml",
    ],

    "research_scientist": [
        "research scientist",
        "researcher in ai",
        "researcher in ml",
    ],

    "nlp_engineer": [
        "nlp engineer",
        "nlp",
        "нлп инженер",
        "nlp инженер",
    ],
}

EXCLUDED_ROLES = [
    "frontend",
    "backend",
    "fullstack",
    "full-stack",
    "android",
    "ios",
    "game designer",
    "game developer",
    "devops",
    "qa",
    "qa engineer",
    "ui/ux",
    "ux/ui",
]

LEVEL_TAXONOMY = {
    "Стажер": [
        "стажер",
        "стажёр",
        "стажировка",
        "intern",
        "internship",
        "trainee",
    ],

    "Джуниор": [
        "junior",
        "джуниор",
        "джун",
        "младший",
    ],

    "Миддл": [
        "middle",
        "миддл",
        "мидл",
    ],

    "Сеньор": [
        "senior",
        "сеньор",
        "синьор",
        "старший",
        "ведущий",
        "principal",
        "staff",
    ],

    "Тимлид/Руководитель группы": [
        "team lead",
        "tech lead",
        "техлид",
        "тимлид",
        "руководитель группы",
        "руководитель команды",
        "lead",
    ],

    "Руководитель отдела/подразделения": [
        "head of",
        "руководитель отдела",
        "руководитель направления",
        "руководитель департамента",
        "начальник отдела",
        "engineering manager",
    ],

    "Директор": [
        "директор",
        "director",
        "cto",
        "cio",
        "ciso",
        "cmo",
        "cdo",
        "chief",
        "ceo",
    ],

    "VP": [
        "vp",
        "vice president",
        "вице-президент",
    ],

    "Архитектор": [
        "архитектор",
        "architect",
    ],

    "Консультант": [
        "консультант",
        "consultant",
    ],
}


# базовый словарь технологий/скиллов для поиска в тексте описания вакансии
# (пополняется по мере находок — сейчас взят из реальных skills_objects getmatch)
SKILLS_VOCABULARY = [
    "python", "java", "kotlin", "go", "golang", "c++", "c#", ".net",
    "javascript", "typescript", "php", "ruby", "scala", "rust",
    "sql", "postgresql", "mysql", "clickhouse", "mongodb", "redis",
    "kafka", "rabbitmq", "airflow",
    "pandas", "numpy", "pytorch", "tensorflow", "scikit-learn", "sklearn",
    "catboost", "xgboost", "lightgbm",
    "docker", "kubernetes", "ci/cd", "linux", "grafana", "prometheus",
    "aws", "gcp", "azure",
    "nlp", "llm", "rag", "computer vision", "deep learning",
    "machine learning", "data science",
    "react", "vue", "angular", "flutter", "kotlin multiplatform",
    "hadoop", "spark", "hive",
]