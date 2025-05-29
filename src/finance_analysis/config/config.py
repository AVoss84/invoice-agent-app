from finance_analysis.services.file import YAMLService

my_yaml = YAMLService(path="finance_analysis/config/input_output.yaml")
io = my_yaml.doRead()

my_yaml2 = YAMLService(path="finance_analysis/config/model_config.yaml")
model_list = my_yaml2.doRead()

my_yaml3 = YAMLService(path="finance_analysis/config/invoice_config.yaml")
invoice_list = my_yaml3.doRead()

my_yaml4 = YAMLService(path="finance_analysis/config/currency.yaml")
currency_list = my_yaml4.doRead()
