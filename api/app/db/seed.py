import json
import logging
from datetime import datetime

from sqlalchemy import select

from .database import SessionLocal
from ..models.department import Department
from ..models.knowledge import KnowledgeArticle
from ..models.student import Student


logger = logging.getLogger(__name__)

DEPARTMENTS = {
    "academic_services": {"department_name": "Academic Services", "email": "academic@example.com", "queue": "academic-support", "sla_default_hours": 12, "requires_human_for_sensitive_actions": True},
    "digital_learning": {"department_name": "Digital Learning Support", "email": "digital-learning@example.com", "queue": "digital-learning", "sla_default_hours": 8, "requires_human_for_sensitive_actions": False},
    "finance": {"department_name": "Financial Services", "email": "finance@example.com", "queue": "financial-operations", "sla_default_hours": 24, "requires_human_for_sensitive_actions": True},
    "career": {"department_name": "Career & Internship", "email": "career@example.com", "queue": "career-support", "sla_default_hours": 48, "requires_human_for_sensitive_actions": False},
    "campus_access": {"department_name": "Campus Access", "email": "campus@example.com", "queue": "campus-access", "sla_default_hours": 4, "requires_human_for_sensitive_actions": True},
    "technology": {"department_name": "Technology Support", "email": "tech@example.com", "queue": "tech-support", "sla_default_hours": 6, "requires_human_for_sensitive_actions": False},
    "student_experience": {"department_name": "Student Experience", "email": "experience@example.com", "queue": "student-experience", "sla_default_hours": 24, "requires_human_for_sensitive_actions": False},
    "library": {"department_name": "Library Services", "email": "library@example.com", "queue": "library-services", "sla_default_hours": 12, "requires_human_for_sensitive_actions": False},
    "other": {"department_name": "General Support", "email": "support@example.com", "queue": "general-inquiries", "sla_default_hours": 24, "requires_human_for_sensitive_actions": False},
}

STUDENTS = [
    {"id": "STU001", "name": "Ari Valen", "course": "Engenharia de Software", "semester": 1, "shift": "matutino", "campus": "Paulista", "email": "stu001@fiap.lab", "status": "active"},
    {"id": "STU002", "name": "Bela Orion", "course": "Ciência da Computação", "semester": 2, "shift": "noturno", "campus": "Vila Mariana", "email": "stu002@fiap.lab", "status": "active"},
    {"id": "STU003", "name": "Cael Nori", "course": "Design Digital", "semester": 3, "shift": "matutino", "campus": "Sorocaba", "email": "stu003@fiap.lab", "status": "active"},
    {"id": "STU004", "name": "Dina Sol", "course": "Administração", "semester": 4, "shift": "noturno", "campus": "Paulista", "email": "stu004@fiap.lab", "status": "active"},
    {"id": "STU005", "name": "Enzo Kair", "course": "Marketing", "semester": 5, "shift": "matutino", "campus": "Vila Mariana", "email": "stu005@fiap.lab", "status": "active"},
    {"id": "STU006", "name": "Fira Lune", "course": "Sistemas de Informação", "semester": 6, "shift": "noturno", "campus": "Sorocaba", "email": "stu006@fiap.lab", "status": "active"},
    {"id": "STU007", "name": "Guto Vale", "course": "Relações Internacionais", "semester": 7, "shift": "matutino", "campus": "Paulista", "email": "stu007@fiap.lab", "status": "active"},
    {"id": "STU008", "name": "Hina Crest", "course": "Engenharia de Produção", "semester": 8, "shift": "noturno", "campus": "Vila Mariana", "email": "stu008@fiap.lab", "status": "active"},
    {"id": "STU009", "name": "Ivo Seren", "course": "Jogos Digitais", "semester": 1, "shift": "matutino", "campus": "Sorocaba", "email": "stu009@fiap.lab", "status": "active"},
    {"id": "STU010", "name": "Jade Corin", "course": "Publicidade e Propaganda", "semester": 2, "shift": "noturno", "campus": "Paulista", "email": "stu010@fiap.lab", "status": "active"},
    {"id": "STU011", "name": "Kaio Ember", "course": "Banco de Dados", "semester": 3, "shift": "matutino", "campus": "Vila Mariana", "email": "stu011@fiap.lab", "status": "active"},
    {"id": "STU012", "name": "Lia Monte", "course": "Análise e Desenvolvimento de Sistemas", "semester": 4, "shift": "noturno", "campus": "Sorocaba", "email": "stu012@fiap.lab", "status": "active"},
    {"id": "STU013", "name": "Miro Taren", "course": "Engenharia de Computação", "semester": 5, "shift": "matutino", "campus": "Paulista", "email": "stu013@fiap.lab", "status": "active"},
    {"id": "STU014", "name": "Nina Quora", "course": "Arquitetura de Soluções", "semester": 6, "shift": "noturno", "campus": "Vila Mariana", "email": "stu014@fiap.lab", "status": "active"},
    {"id": "STU015", "name": "Otto Ravin", "course": "Ciência de Dados", "semester": 7, "shift": "matutino", "campus": "Sorocaba", "email": "stu015@fiap.lab", "status": "active"},
    {"id": "STU016", "name": "Pia Neru", "course": "UX Design", "semester": 8, "shift": "noturno", "campus": "Paulista", "email": "stu016@fiap.lab", "status": "inactive"},
    {"id": "STU017", "name": "Quin Sora", "course": "Gestão Financeira", "semester": 2, "shift": "matutino", "campus": "Vila Mariana", "email": "stu017@fiap.lab", "status": "active"},
    {"id": "STU018", "name": "Rina Mav", "course": "Comércio Exterior", "semester": 3, "shift": "noturno", "campus": "Sorocaba", "email": "stu018@fiap.lab", "status": "active"},
    {"id": "STU019", "name": "Sami Lior", "course": "Engenharia Mecatrônica", "semester": 4, "shift": "matutino", "campus": "Paulista", "email": "stu019@fiap.lab", "status": "active"},
    {"id": "STU020", "name": "Tali Noven", "course": "Economia Criativa", "semester": 5, "shift": "noturno", "campus": "Vila Mariana", "email": "stu020@fiap.lab", "status": "inactive"},
]


def _didactic_content(text: str) -> str:
    return f"{text} Conteúdo fictício para fins didáticos."


KNOWLEDGE_ARTICLES = [
    {"id": "KB001", "title": "How to access the digital learning environment", "category": "digital_learning", "keywords": ["ambiente", "virtual", "acesso", "login", "learning"], "content": _didactic_content("Para este laboratório, o acesso ao ambiente digital é simulado por um portal acadêmico fictício com login de estudante e redefinição orientada do acesso."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 10, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB002", "title": "How to request an enrollment declaration", "category": "academic_services", "keywords": ["declaração", "matrícula", "solicitação", "documento"], "content": _didactic_content("Neste cenário fictício, a declaração de matrícula é solicitada por formulário acadêmico e passa por conferência manual antes da emissão."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 11, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB003", "title": "Understanding your tuition invoice", "category": "finance", "keywords": ["mensalidade", "fatura", "boleto", "invoice", "pagamento"], "content": _didactic_content("A fatura simulada deste laboratório apresenta vencimento, referência e orientação de leitura, mas qualquer ajuste depende de atendimento humano fictício."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 12, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB004", "title": "Internship information", "category": "career", "keywords": ["estágio", "carreira", "internship", "currículo", "vaga"], "content": _didactic_content("O fluxo didático de estágio mostra onde localizar oportunidades, registrar interesse e acompanhar próximas etapas em uma trilha fictícia."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 13, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB005", "title": "Lab access issues", "category": "campus_access", "keywords": ["laboratório", "acesso", "catraca", "campus", "entrada"], "content": _didactic_content("Se o acesso ao laboratório falhar neste exercício, o estudante deve registrar a ocorrência e aguardar triagem da equipe de acesso em um processo inteiramente fictício."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 14, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB006", "title": "Wi-Fi troubleshooting", "category": "technology", "keywords": ["wifi", "rede", "internet", "conexão", "tecnologia"], "content": _didactic_content("A base didática orienta checar credenciais, reiniciar conexão e confirmar o perfil de acesso da rede acadêmica fictícia."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 15, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB007", "title": "Upcoming events and activities", "category": "student_experience", "keywords": ["eventos", "atividades", "experiência", "agenda", "campus"], "content": _didactic_content("Os eventos mostrados nesta API representam atividades acadêmicas simuladas que ajudam a praticar filtros e automações."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 16, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB008", "title": "Library resource access", "category": "library", "keywords": ["biblioteca", "livros", "acervo", "recurso", "acesso"], "content": _didactic_content("O artigo ensina como consultar um acervo fictício, localizar recursos digitais simulados e abrir chamados quando houver indisponibilidade."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 17, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB009", "title": "Updating contact details in the portal", "category": "academic_services", "keywords": ["cadastro", "contato", "telefone", "email", "portal"], "content": _didactic_content("Neste fluxo fictício, dados cadastrais simples podem ser conferidos no portal e enviados para atualização por solicitação acadêmica."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 18, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB010", "title": "Resetting your portal password", "category": "digital_learning", "keywords": ["senha", "reset", "portal", "login", "credencial"], "content": _didactic_content("A redefinição de senha do portal segue um passo a passo simulado com confirmação por e-mail fictício e nova autenticação."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 19, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB011", "title": "Payment agreement simulation", "category": "finance", "keywords": ["acordo", "pagamento", "negociação", "financeiro", "mensalidade"], "content": _didactic_content("O conteúdo explica um cenário didático de negociação financeira, sem reproduzir políticas reais e sempre com validação humana."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 20, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB012", "title": "Preparing for mock interviews", "category": "career", "keywords": ["entrevista", "mock", "carreira", "preparação", "portfólio"], "content": _didactic_content("O laboratório simula orientações de carreira para entrevistas, revisão de portfólio e preparação pessoal em ambiente controlado."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 21, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB013", "title": "Temporary campus badge issue", "category": "campus_access", "keywords": ["crachá", "temporário", "acesso", "campus", "badge"], "content": _didactic_content("Quando o crachá temporário fictício falha, o estudante pode abrir solicitação para análise rápida do time de acesso do campus."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 22, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB014", "title": "Classroom projector support", "category": "technology", "keywords": ["projetor", "sala", "equipamento", "tecnologia", "suporte"], "content": _didactic_content("O procedimento fictício recomenda validar cabos, entrada de vídeo e reinicialização antes de acionar suporte técnico acadêmico."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 23, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB015", "title": "Student club participation", "category": "student_experience", "keywords": ["clube", "participação", "comunidade", "experiência", "atividade"], "content": _didactic_content("Este artigo fictício mostra como registrar interesse em clubes estudantis e acompanhar confirmações automáticas de participação."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 24, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB016", "title": "Borrowing library equipment", "category": "library", "keywords": ["empréstimo", "equipamento", "biblioteca", "reserva", "tablet"], "content": _didactic_content("O empréstimo de equipamentos é tratado aqui como processo fictício com reserva, retirada e devolução monitoradas pelo laboratório."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 25, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB017", "title": "Grade review guidance", "category": "academic_services", "keywords": ["nota", "revisão", "avaliação", "disciplina", "acadêmico"], "content": _didactic_content("A revisão de nota é apresentada como procedimento didático, com justificativa estruturada e tratamento manual pela área acadêmica fictícia."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 26, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB018", "title": "Downloading class materials", "category": "digital_learning", "keywords": ["materiais", "download", "aula", "arquivo", "virtual"], "content": _didactic_content("Os materiais de aula simulados ficam em uma área digital fictícia com filtros por disciplina e semestre."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 27, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB019", "title": "Invoice due date questions", "category": "finance", "keywords": ["vencimento", "fatura", "financeiro", "dúvida", "boleto"], "content": _didactic_content("A base responde dúvidas gerais sobre vencimento em cenário fictício, mas qualquer alteração é direcionada a análise humana didática."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 28, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB020", "title": "Career fair registration", "category": "career", "keywords": ["feira", "carreira", "inscrição", "evento", "networking"], "content": _didactic_content("A inscrição em feira de carreiras deste laboratório segue um processo automatizado de demonstração com confirmação fictícia."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 29, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB021", "title": "Visitor access request", "category": "campus_access", "keywords": ["visitante", "acesso", "campus", "autorização", "entrada"], "content": _didactic_content("Pedidos de visitante são apenas exemplos didáticos e exigem aprovação humana simulada por envolver ação sensível de acesso."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 1, 30, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB022", "title": "Account unlock for lab systems", "category": "technology", "keywords": ["desbloqueio", "conta", "sistema", "lab", "tecnologia"], "content": _didactic_content("O desbloqueio de conta acadêmica é simulado com validações técnicas básicas antes do escalonamento do atendimento."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 1, 31, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB023", "title": "Well-being support channels", "category": "student_experience", "keywords": ["bem-estar", "acolhimento", "apoio", "experiência", "canal"], "content": _didactic_content("Os canais de acolhimento deste caso são totalmente fictícios e servem apenas para exercitar triagem e roteamento de solicitações."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 1, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB024", "title": "Accessing digital journals", "category": "library", "keywords": ["periódicos", "journals", "biblioteca", "digital", "acesso"], "content": _didactic_content("O acesso a periódicos digitais simulados passa por portal de biblioteca fictício com instruções simples de consulta."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 2, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB025", "title": "General support request routing", "category": "other", "keywords": ["geral", "suporte", "roteamento", "categoria", "outros"], "content": _didactic_content("Quando a categoria não estiver clara, a API didática encaminha a solicitação para suporte geral até nova classificação."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 3, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB026", "title": "Transfer request orientation", "category": "academic_services", "keywords": ["transferência", "orientação", "acadêmico", "curso", "campus"], "content": _didactic_content("A orientação de transferência apresentada aqui não representa política institucional real e depende de análise humana fictícia."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 4, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB027", "title": "Streaming class playback issue", "category": "digital_learning", "keywords": ["streaming", "aula", "reprodução", "vídeo", "digital"], "content": _didactic_content("Se a aula gravada fictícia não reproduzir, o estudante deve testar navegador, cache e conexão antes de abrir uma interação."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 5, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB028", "title": "Scholarship statement guidance", "category": "finance", "keywords": ["bolsa", "comprovante", "financeiro", "declaração", "benefício"], "content": _didactic_content("Este artigo descreve um comprovante financeiro fictício e direciona demandas sensíveis para validação humana do laboratório."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 6, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB029", "title": "Mentorship program overview", "category": "career", "keywords": ["mentoria", "programa", "carreira", "desenvolvimento", "networking"], "content": _didactic_content("O programa de mentoria mostrado na API é ilustrativo e serve para demonstrar recomendações automáticas de carreira."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 7, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB030", "title": "Noise complaint in study area", "category": "library", "keywords": ["barulho", "estudo", "biblioteca", "ocorrência", "silêncio"], "content": _didactic_content("A ocorrência de barulho em área de estudo é um exemplo de atendimento fictício com registro, mediação e possível apoio humano."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 8, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB031", "title": "VPN connection guide", "category": "technology", "keywords": ["vpn", "conexão", "remoto", "acesso", "segurança"], "content": _didactic_content("O guia de conexão VPN orienta a instalação do cliente, configuração de perfil e solução de problemas de conectividade remota."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 9, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB032", "title": "Software installation request", "category": "technology", "keywords": ["software", "instalação", "aplicativo", "programa", "solicitacao"], "content": _didactic_content("Para solicitar instalação de software educacional, o estudante deve preencher formulário com justificativa e aguardar aprovação técnica."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 10, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB033", "title": "Academic transcript request", "category": "academic_services", "keywords": ["historico", "transcricao", "documento", "academico", "formatura"], "content": _didactic_content("A solicitação de historico acadêmico é processada electronicamente e disponibilizada para download após validação."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 11, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB034", "title": "Course enrollment period", "category": "academic_services", "keywords": ["matricula", "periodo", "disciplina", "grade", "horario"], "content": _didactic_content("O periodo de matrícula é informado com antecedência e o estudante deve verificar conflitos de horário antes de confirmar."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 12, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB035", "title": "Study room reservation", "category": "library", "keywords": ["sala", "estudo", "reserva", "grupo", "biblioteca"], "content": _didactic_content("Salas de estudo podem ser reservadas pelo portal com antecedência máxima de 7 dias e duração de 2 horas."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 13, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB036", "title": "Interlibrary loan request", "category": "library", "keywords": ["emprestimo", "interbibliotecario", "livro", "requisicao", "biblioteca"], "content": _didactic_content("O empréstimo interbibliotecário permite solicitar livros de outras unidades com prazo de entrega de até 10 dias úteis."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 14, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB037", "title": "Resume building workshop", "category": "career", "keywords": ["curriculo", "workshop", "carreira", "formatacao", "profissional"], "content": _didactic_content("Workshops de curriculo ajudam estudantes a formatar documentos profissionais seguindo padrões do mercado."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 15, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB038", "title": "Job board access", "category": "career", "keywords": ["vaga", "emprego", "trabalho", "oportunidade", "carreira"], "content": _didactic_content("A plataforma de vagas conecta estudantes a oportunidades de estágio e emprego com filtros por área e localização."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 16, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB039", "title": "Parking pass request", "category": "campus_access", "keywords": ["estacionamento", "veiculo", "cracha", "acesso", "campus"], "content": _didactic_content("A solicitação de crachá de estacionamento requer comprovação de veículo e aprovação do departamento de acesso."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 17, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB040", "title": "Building access hours", "category": "campus_access", "keywords": ["horario", "predio", "acesso", "campus", "funcionamento"], "content": _didactic_content("Os horários de acesso aos prédios acadêmicos variam por campus e período letivo, com extensões durante provas."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 18, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB041", "title": "Student organization registration", "category": "student_experience", "keywords": ["organizacao", "estudantil", "grupo", "comunidade", "registro"], "content": _didactic_content("Organizações estudantis podem registrar novos membros pelo portal com validação automática de elegibilidade."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 19, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB042", "title": "Campus event submission", "category": "student_experience", "keywords": ["evento", "submissao", "atividade", "campus", "organizacao"], "content": _didactic_content("Eventos acadêmicos podem ser submetidos para aprovação com antecedência mínima de 15 dias."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 20, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB043", "title": "Tuition payment plan", "category": "finance", "keywords": ["parcelamento", "pagamento", "mensalidade", "acordo", "financeiro"], "content": _didactic_content("Planos de parcelamento estão disponíveis para estudantes com dificuldades financeiras, sujeitos a aprovação."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 21, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB044", "title": "Fee exemption application", "category": "finance", "keywords": ["isencao", "taxa", "bolsa", "beneficio", "solicitacao"], "content": _didactic_content("Estudantes podem solicitar isenção de taxas administrativas com documentação comprobatória."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 22, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB045", "title": "Online exam platform access", "category": "digital_learning", "keywords": ["prova", "online", "plataforma", "exame", "avaliacao"], "content": _didactic_content("A plataforma de provas online requer autenticação dupla e verificação de identidade antes da início."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 23, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB046", "title": "Group project collaboration tools", "category": "digital_learning", "keywords": ["grupo", "projeto", "colaboracao", "ferramenta", "trabalho"], "content": _didactic_content("Ferramentas de colaboração são disponibilizadas para trabalhos em grupo com versionamento e compartilhamento de arquivos."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 24, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB047", "title": "Library fines inquiry", "category": "library", "keywords": ["multa", "atraso", "devolucao", "biblioteca", "cobranca"], "content": _didactic_content("Multas por atraso na devolução de materiais podem ser consultadas e parceladas pelo portal."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 25, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB048", "title": "Career mentoring sessions", "category": "career", "keywords": ["mentoria", "sessao", "carreira", "orientacao", "profissional"], "content": _didactic_content("Sessões de mentoria são agendadas automaticamente com profissionais parceiros da área de atuação do estudante."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 26, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB049", "title": "Student ID card replacement", "category": "campus_access", "keywords": ["cracha", "substituicao", "perda", "roubo", "identidade"], "content": _didactic_content("A substituição do crachá de estudante requer registro de ocorrência e emissão de novo documento."), "can_answer_automatically": False, "requires_human": True, "last_updated": datetime(2026, 2, 27, 9, 0, 0), "source_type": "didactic"},
    {"id": "KB050", "title": "Mental health resources", "category": "student_experience", "keywords": ["saude", "mental", "bem-estar", "apoio", "psicologico"], "content": _didactic_content("Recursos de saúde mental são disponibilizados com canais de escuta e encaminhamento para profissionais especializados."), "can_answer_automatically": True, "requires_human": False, "last_updated": datetime(2026, 2, 28, 9, 0, 0), "source_type": "didactic"},
]


def list_students() -> list[dict[str, object]]:
    return [dict(student) for student in STUDENTS]


def get_student(student_id: str) -> dict[str, object] | None:
    normalized_student_id = student_id.strip().upper()
    return next((dict(student) for student in STUDENTS if student["id"] == normalized_student_id), None)


def list_departments() -> list[dict[str, object]]:
    return [{"category": category, **department} for category, department in DEPARTMENTS.items()]


def get_department(category: str) -> dict[str, object] | None:
    normalized_category = category.strip().lower()
    department = DEPARTMENTS.get(normalized_category)
    if department is None:
        return None
    return {"category": normalized_category, **department}


def list_knowledge_articles(category: str | None = None) -> list[dict[str, object]]:
    if category is None:
        return [dict(article) for article in KNOWLEDGE_ARTICLES]
    normalized_category = category.strip().lower()
    return [dict(article) for article in KNOWLEDGE_ARTICLES if article["category"] == normalized_category]


def get_knowledge_article(article_id: str) -> dict[str, object] | None:
    normalized_article_id = article_id.strip().upper()
    return next((dict(article) for article in KNOWLEDGE_ARTICLES if article["id"] == normalized_article_id), None)


def seed_data() -> None:
    db = SessionLocal()
    try:
        student_exists = db.execute(select(Student.id).limit(1)).scalar_one_or_none()
        department_exists = db.execute(select(Department.category).limit(1)).scalar_one_or_none()
        knowledge_exists = db.execute(select(KnowledgeArticle.id).limit(1)).scalar_one_or_none()

        if not student_exists:
            db.add_all(Student(**student_data) for student_data in STUDENTS)
            logger.info("Seeded %s fictional students", len(STUDENTS))

        if not department_exists:
            db.add_all(
                Department(category=category, **department_data)
                for category, department_data in DEPARTMENTS.items()
            )
            logger.info("Seeded %s departments", len(DEPARTMENTS))

        if not knowledge_exists:
            db.add_all(
                KnowledgeArticle(
                    id=article_data["id"],
                    title=article_data["title"],
                    category=article_data["category"],
                    keywords=json.dumps(article_data["keywords"], ensure_ascii=False),
                    content=article_data["content"],
                    can_answer_automatically=article_data["can_answer_automatically"],
                    requires_human=article_data["requires_human"],
                    last_updated=article_data["last_updated"],
                    source_type=article_data["source_type"],
                )
                for article_data in KNOWLEDGE_ARTICLES
            )
            logger.info("Seeded %s knowledge articles", len(KNOWLEDGE_ARTICLES))

        if not student_exists or not department_exists or not knowledge_exists:
            db.commit()
        else:
            logger.info("Seed data already present; skipping")
    except Exception:
        db.rollback()
        logger.exception("Failed to seed database")
        raise
    finally:
        db.close()
