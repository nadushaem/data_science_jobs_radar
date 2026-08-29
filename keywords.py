TARGET_KEYWORDS = {
    "healthtech": [
        "healthtech", "health tech", "digital health", "digital healthcare",
        "медицина", "медицин", "здравоохран", "healthcare",
    ],
    "medtech": [
        "medtech", "med tech", "медтех", "медицинское оборудование", "medical device",
    ],
    "femtech": [
        "femtech", "женское здоровье", "women's health", "women health",
        "fertility", "репродуктив", "гинеколог",
    ],
    "fintech": [
        "fintech", "финтех", "финансовые технологии", "платежный сервис",
        "платежные системы", "payments", "банкинг",
    ],
    "edtech": [
        "edtech", "эдтех", "образовательные технологии",
        "онлайн-образование", "online education", "education",
    ],
    "hrtech": [
        "hrtech", "hr tech", "hr-tech", "кадровые технологии", "recruiting tech",
    ],
    "adtech": [
        "adtech", "ad tech", "martech", "mar tech",
        "рекламные технологии", "programmatic",
    ],
    "gamedev": [
        "gamedev", "game dev", "геймдев", "игровая индустрия", "games industry",
    ],
    "logistics": [
        "logistics", "логистика", "логистическая", "supply chain",
        "cargo", "delivery tech",
    ],
    "ecommerce": [
        "e-commerce", "ecommerce", "интернет-магазин", "интернет магазин",
        "маркетплейс", "marketplace", "онлайн-ритейл", "online retail",
    ],
}

INDUSTRY_LABELS = {
    "healthtech": "Healthtech",
    "medtech": "Medtech",
    "femtech": "Femtech",
    "fintech": "Fintech",
    "edtech": "Edtech",
    "hrtech": "HRtech",
    "adtech": "Adtech/Martech",
    "gamedev": "Gamedev",
    "logistics": "Логистика",
    "ecommerce": "E-commerce",
}

# человекочитаемые названия сфер — используются и в кнопках бота,
# и в подписи сводки. порядок словаря = порядок кнопок в /industries
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

    "data_governance": [
        "data governance analyst",
        "data governance specialist",
        "специалист по управлению данными",
        "аналитик по управлению данными",
        "data governance engineer",
    ],

    "data_quality": [
        "data steward",
        "дата стюард",
        "дата-стюард",
        "стюард данных",
        "data quality analyst",
        "data quality engineer",
        "data quality specialist",
        "специалист по качеству данных",
        "аналитик по качеству данных",
        "инженер по качеству данных",
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

    "cv_engineer": [
        "cv engineer",
        "computer vision engineer",
        "computer-vision engineer",
        "инженер компьютерного зрения",
        "cv-инженер",
        "cv инженер",
    ],

    "data_analyst": [
        "data analyst",
        "дата аналитик",
        "дата-аналитик",
        "аналитик данных",
    ],

    "data_engineer": [
        "data engineer",
        "дата инженер",
        "дата-инженер",
        "инженер данных",
    ],
}

ROLE_LABELS = {
    "data_scientist": "Data Scientist",
    "ml_engineer": "ML Engineer",
    "ai_ml_engineer": "AI/ML Engineer",
    "data_engineer": "Data Engineer",
    "data_analyst": "Data Analyst",
    "cv_engineer": "CV Engineer",
    "nlp_engineer": "NLP Engineer",
    "research_scientist": "Research Scientist",
    "data_governance": "Data Governance",
    "data_quality": "Data Quality",
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