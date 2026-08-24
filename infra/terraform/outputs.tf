output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "vm_name" {
  value = azurerm_linux_virtual_machine.this.name
}

output "public_ip_address" {
  description = "IP público da VM. Cria aqui o registo DNS A do domínio."
  value       = azurerm_public_ip.this.ip_address
}

output "ssh_command" {
  description = "Comando pronto a usar para SSH à VM."
  value       = "ssh -i ./ssh/hopin_vm_key ${var.admin_username}@${azurerm_public_ip.this.ip_address}"
}

output "data_disk_mount" {
  value = "/data (dispositivo /dev/disk/azure/scsi1/lun0-part1)"
}

output "site_domain" {
  description = <<-EOT
    Hostname a usar em VIRTUAL_HOST/LETSENCRYPT_HOST no env.web da VM. Se
    não deste domain_name, é o hostname sslip.io gerado automaticamente a
    partir do IP público.
  EOT
  value       = local.effective_domain
}
