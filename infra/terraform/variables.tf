variable "prefix" {
  description = "Prefixo usado no nome de todos os recursos."
  type        = string
  default     = "hopin"
}

variable "location" {
  description = "Região Azure onde os recursos são criados."
  type        = string
  default     = "westeurope"
}

variable "environment" {
  description = "Tag de ambiente (ex: poc, staging, production)."
  type        = string
  default     = "poc"
}

variable "vm_size" {
  description = <<-EOT
    Tamanho da VM. Standard_B2s (2 vCPU / 4GB RAM, ~28€/mês em West Europe) chega
    para a PoC (Django + Huey + Postgres + Redis + Nginx no mesmo host, tráfego
    baixo). Se sentires lentidão, sobe para Standard_B2ms (4 vCPU / 8GB, ~60€/mês)
    — ainda dentro do limite de 80€/mês.
  EOT
  type        = string
  default     = "Standard_B2s"
}

variable "admin_username" {
  description = "Utilizador administrador criado na VM (login SSH)."
  type        = string
  default     = "hopinadmin"
}

variable "ssh_public_key_path" {
  description = <<-EOT
    Caminho local para a chave pública SSH a instalar na VM. Gera o par de
    chaves antes do `terraform apply` (ver README.md deste diretório).
  EOT
  type        = string
  default     = "./ssh/hopin_vm_key.pub"
}

variable "allowed_ssh_cidrs" {
  description = <<-EOT
    Lista de CIDRs autorizados a fazer SSH (porta 22) à VM. Usa o teu IP
    público atual em formato /32 (ex: ["203.0.113.10/32"]). NÃO deixes
    ["0.0.0.0/0"] em produção — só para testes muito curtos.
  EOT
  type        = list(string)
}

variable "os_disk_size_gb" {
  description = "Tamanho do disco de SO em GB."
  type        = number
  default     = 32
}

variable "data_disk_size_gb" {
  description = <<-EOT
    Tamanho do disco de dados em GB, montado em /data. Aqui deve ficar o
    volume Docker do Postgres (danceschool_postgres) e os media/static files,
    para poderes crescer ou fazer snapshot/backup independentemente do disco
    de SO.
  EOT
  type        = number
  default     = 32
}

variable "domain_name" {
  description = <<-EOT
    Domínio final do site (ex: hopin.pt ou app.hopin.pt). Deixa em branco se
    ainda não tiveres o domínio decidido — podes configurar depois via SSH.
    Depois do `apply`, cria um registo DNS A a apontar para o output
    `public_ip_address`.
  EOT
  type        = string
  default     = ""
}

variable "acme_email" {
  description = "Email usado para os certificados Let's Encrypt (LETSENCRYPT_EMAIL)."
  type        = string
  default     = ""
}

variable "github_repo_url" {
  description = "URL do repositório a clonar para /opt/hopin/app na VM."
  type        = string
  default     = "https://github.com/pedrobsm/django_dance_school.git"
}

variable "ghcr_image" {
  description = "Referência da imagem Docker publicada por CI para o container web/huey."
  type        = string
  default     = "ghcr.io/pedrobsm/danceschool-web:latest"
}

variable "ghcr_username" {
  description = <<-EOT
    Utilizador GitHub para `docker login ghcr.io`, caso o package seja
    privado. Deixa em branco para saltar o login (necessário se a imagem
    ghcr.io/pedrobsm/danceschool-web for privada).
  EOT
  type        = string
  default     = ""
}

variable "ghcr_token" {
  description = <<-EOT
    Personal Access Token (classic ou fine-grained, scope `read:packages`)
    para autenticar em ghcr.io. Passa via variável de ambiente
    TF_VAR_ghcr_token, nunca commitado em terraform.tfvars.
  EOT
  type        = string
  default     = ""
  sensitive   = true
}
