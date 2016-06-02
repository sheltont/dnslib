oversea.ceair.com.       3600        IN      SOA     ns1.oversea.ceair.com. admin.ceair.com. 2016060110 7200 3600 1209600 3600
ns1.oversea.ceair.com.   3600        IN      A       114.179.12.183
oversea.ceair.com.       3600        IN      NS      10      ns1.oversea.ceair.com
oversea.ceair.com.       3600        IN      TXT     "v=spf1 ip4:218.1.115.9 ip4:218.1.115.8 ip4:180.166.149.193 ip4:63.220.5.51 ip4:63.220.5.53 ip4:222.66.97.77  ip4:218.80.232.48   ip4:218.80.232.48 ip4:221.189.114.89 ~all"
oversea.ceair.com.       3600        IN      MX      100       218.1.115.9
oversea.ceair.com.       3600        IN      MX      10      114.179.12.181
