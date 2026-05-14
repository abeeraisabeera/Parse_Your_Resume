export const DEFAULT_MODEL = "llama-3.1-8b-instant";

export const ROLE_DEFINITIONS = [
  { id: "all", label: "All roles", shortLabel: "All", category: "System" },
  { id: "frontend", label: "Frontend Developer", shortLabel: "Frontend", category: "Engineering" },
  { id: "backend", label: "Backend Developer", shortLabel: "Backend", category: "Engineering" },
  { id: "fullstack", label: "Fullstack Developer", shortLabel: "Fullstack", category: "Engineering" },
  { id: "data", label: "Data Scientist / BI", shortLabel: "Data", category: "Data / AI" },
  { id: "devops", label: "DevOps / Cloud", shortLabel: "DevOps", category: "Infrastructure" },
  { id: "qa", label: "QA / Testing", shortLabel: "QA", category: "Quality" },
  { id: "design", label: "UI/UX Designer", shortLabel: "Design", category: "Creative" },
  { id: "marketing", label: "Marketing", shortLabel: "Marketing", category: "Growth" },
  { id: "hr", label: "Human Resources", shortLabel: "HR", category: "Operations" },
  { id: "sales", label: "Sales", shortLabel: "Sales", category: "Revenue" },
  { id: "product", label: "Product Manager", shortLabel: "Product", category: "Product" },
  { id: "general", label: "General", shortLabel: "General", category: "General" }
];

export const ROLE_OPTIONS = ROLE_DEFINITIONS.map((role) => [role.id, role.label]);

export const DEFAULT_SKILL_GROUPS = [
  {
    label: "Frontend",
    role: "frontend",
    options: [
      ["react", "React"],
      ["next.js", "Next.js"],
      ["typescript", "TypeScript"],
      ["javascript", "JavaScript"],
      ["vue", "Vue"],
      ["angular", "Angular"],
      ["tailwind", "Tailwind CSS"],
      ["redux", "Redux"],
      ["react query", "React Query"],
      ["web accessibility", "Accessibility"]
    ]
  },
  {
    label: "Backend",
    role: "backend",
    options: [
      ["node.js", "Node.js"],
      ["express", "Express"],
      ["python", "Python"],
      ["django", "Django"],
      ["fastapi", "FastAPI"],
      ["java", "Java"],
      ["spring", "Spring Boot"],
      ["postgresql", "PostgreSQL"],
      ["mongodb", "MongoDB"],
      ["redis", "Redis"],
      ["graphql", "GraphQL"],
      ["rest api", "REST API"]
    ]
  },
  {
    label: "Data / AI",
    role: "data",
    options: [
      ["sql", "SQL"],
      ["pandas", "Pandas"],
      ["numpy", "NumPy"],
      ["spark", "Spark"],
      ["airflow", "Airflow"],
      ["dbt", "dbt"],
      ["machine learning", "Machine Learning"],
      ["llm", "LLM"],
      ["rag", "RAG"],
      ["tensorflow", "TensorFlow"],
      ["pytorch", "PyTorch"],
      ["power bi", "Power BI"]
    ]
  },
  {
    label: "DevOps / QA",
    role: "devops",
    options: [
      ["aws", "AWS"],
      ["azure", "Azure"],
      ["gcp", "GCP"],
      ["docker", "Docker"],
      ["kubernetes", "Kubernetes"],
      ["terraform", "Terraform"],
      ["ci/cd", "CI/CD"],
      ["selenium", "Selenium"],
      ["playwright", "Playwright"],
      ["cypress", "Cypress"],
      ["jmeter", "JMeter"]
    ]
  },
  {
    label: "Design / Marketing",
    role: "design",
    options: [
      ["figma", "Figma"],
      ["photoshop", "Photoshop"],
      ["illustrator", "Illustrator"],
      ["design systems", "Design Systems"],
      ["seo", "SEO"],
      ["google analytics", "Google Analytics"],
      ["google ads", "Google Ads"],
      ["crm", "CRM"],
      ["shopify", "Shopify"]
    ]
  }
];

export const DEFAULT_SKILLS = DEFAULT_SKILL_GROUPS.flatMap((group) =>
  group.options.map(([id, label]) => ({
    id,
    label,
    category: group.label,
    roles: [group.role].filter(Boolean),
    aliases: []
  }))
);

export const SENIORITY_OPTIONS = ["intern", "junior", "mid", "senior", "lead", "unknown"];
