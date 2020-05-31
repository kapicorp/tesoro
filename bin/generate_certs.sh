openssl genrsa -out rootCA.key 4096
openssl req -x509 -new -nodes -key rootCA.key -subj "/CN=CA-tesoro-admission-controller.tesoro.svc" -sha256 -days 1024 -out rootCA.crt
openssl genrsa -out priv.key 2048
openssl req -new -sha256 -key priv.key -subj "/CN=tesoro-admission-controller.tesoro.svc" -out csr.csr
openssl x509 -req -in csr.csr -CA rootCA.crt -CAkey rootCA.key -CAcreateserial -out cert.pem -days 500 -sha256
openssl x509 -in cert.pem -text -noout
