locals {
  tags = {
    project     = "hopin"
    environment = var.environment
    managed_by  = "terraform"
  }

  # Se não deres um domínio próprio, usa um hostname sslip.io derivado do IP
  # público — resolve automaticamente para esse IP sem configurar DNS
  # nenhum, e o Let's Encrypt emite certificados normais para ele (não está
  # na Public Suffix List, mas tem uma quota partilhada elevada concedida
  # pela Let's Encrypt especificamente para este uso). Suficiente para a
  # PoC; troca por um domínio real quando/se a HOP IN decidir avançar.
  effective_domain = var.domain_name != "" ? var.domain_name : "${replace(azurerm_public_ip.this.ip_address, ".", "-")}.sslip.io"
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.prefix}-${var.environment}"
  location = var.location
  tags     = local.tags
}

# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${var.prefix}-${var.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  address_space       = ["10.20.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "this" {
  name                 = "snet-${var.prefix}-${var.environment}"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.20.1.0/24"]
}

resource "azurerm_network_security_group" "this" {
  name                = "nsg-${var.prefix}-${var.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags

  security_rule {
    name                       = "AllowSSH"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefixes    = var.allowed_ssh_cidrs
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowHTTP"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowHTTPS"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "this" {
  subnet_id                 = azurerm_subnet.this.id
  network_security_group_id = azurerm_network_security_group.this.id
}

resource "azurerm_public_ip" "this" {
  name                = "pip-${var.prefix}-${var.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_network_interface" "this" {
  name                = "nic-${var.prefix}-${var.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.this.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.this.id
  }
}

# ---------------------------------------------------------------------------
# Disco de dados (Postgres, media/static, backups) — separado do SO para
# poderes fazer snapshot/resize sem tocar na VM.
# ---------------------------------------------------------------------------

resource "azurerm_managed_disk" "data" {
  name                 = "disk-${var.prefix}-${var.environment}-data"
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  storage_account_type = "StandardSSD_LRS"
  create_option        = "Empty"
  disk_size_gb         = var.data_disk_size_gb
  tags                 = local.tags
}

resource "azurerm_virtual_machine_data_disk_attachment" "data" {
  managed_disk_id    = azurerm_managed_disk.data.id
  virtual_machine_id = azurerm_linux_virtual_machine.this.id
  lun                = 0
  caching             = "ReadWrite"
}

# ---------------------------------------------------------------------------
# VM
# ---------------------------------------------------------------------------

resource "azurerm_linux_virtual_machine" "this" {
  name                            = "vm-${var.prefix}-${var.environment}"
  resource_group_name             = azurerm_resource_group.this.name
  location                        = azurerm_resource_group.this.location
  size                            = var.vm_size
  admin_username                  = var.admin_username
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.this.id]
  tags                            = local.tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = file(var.ssh_public_key_path)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb          = var.os_disk_size_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tpl", {
    admin_username   = var.admin_username
    github_repo_url  = var.github_repo_url
    ghcr_image       = var.ghcr_image
    ghcr_username    = var.ghcr_username
    ghcr_token       = var.ghcr_token
    domain_name      = local.effective_domain
    acme_email       = var.acme_email
  }))

  boot_diagnostics {
    storage_account_uri = null
  }
}
