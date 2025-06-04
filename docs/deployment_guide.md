# Nebula AI 배포 가이드

## 개요

이 문서는 Nebula AI 시스템을 다양한 환경(로컬, 개발, 스테이징, 프로덕션)에 배포하는 방법을 설명합니다. Docker와 Kubernetes를 활용한 컨테이너 기반 배포를 중심으로 하며, 확장성과 안정성을 고려한 배포 전략을 포함합니다.

## 시스템 요구사항

### 최소 하드웨어 요구사항

#### 개발 환경
- **CPU**: 2 코어 이상
- **메모리**: 8GB RAM 이상
- **디스크**: 20GB 여유 공간
- **네트워크**: 인터넷 연결 필수

#### 프로덕션 환경
- **CPU**: 4 코어 이상 (8 코어 권장)
- **메모리**: 16GB RAM 이상 (32GB 권장)
- **디스크**: 100GB SSD 이상
- **네트워크**: 고속 인터넷 연결

### 소프트웨어 요구사항

#### 필수 소프트웨어
- **Docker**: 20.10+ (Docker Compose 포함)
- **Python**: 3.11+
- **Node.js**: 18+ (모니터링 도구용)
- **Git**: 2.30+

#### 선택 소프트웨어
- **Kubernetes**: 1.25+ (프로덕션 배포 시)
- **Helm**: 3.10+ (Kubernetes 배포 시)
- **Terraform**: 1.0+ (인프라 관리 시)

---

## 환경별 배포 가이드

### 1. 로컬 개발 환경

로컬 개발을 위한 가장 간단한 배포 방법입니다.

#### 설정
```bash
# 1. 프로젝트 클론
git clone <repository-url>
cd nebula-ai

# 2. 환경 변수 설정
cp env.example .env
# .env 파일을 편집하여 필요한 API 키 등을 설정

# 3. 개발용 서비스 시작
make local

# 4. 서비스 확인
make test-services
```

#### 환경 변수 설정 (.env)
```bash
# 개발 환경용 설정
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# 데이터베이스 (로컬)
DATABASE_URL=postgresql://postgres:password@localhost:5433/nebula_ai
REDIS_URL=redis://localhost:6380/0

# 메시지 큐 (로컬)
RABBITMQ_URL=amqp://guest:guest@localhost:5673//

# API 키들
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# AWS (테스트용)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_KEY_ID=your_aws_secret_key
BUCKET_NAME=nebula-ai-dev
```

### 2. Docker Compose 배포

#### 기본 Docker Compose 배포
```bash
# 1. 프로덕션용 환경 변수 설정
cp env.example .env.prod

# 2. 전체 스택 시작
docker-compose up -d

# 3. 서비스 상태 확인
docker-compose ps
docker-compose logs -f
```

#### docker-compose.yml 구성
```yaml
version: '3.8'

services:
  # AI 서버 (FastAPI)
  ai-server:
    build:
      context: .
      dockerfile: docker/ai-server/Dockerfile
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.prod
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - rabbitmq
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  # Celery Worker
  celery-worker:
    build:
      context: .
      dockerfile: docker/celery/Dockerfile
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.prod
    depends_on:
      - postgres
      - redis
      - rabbitmq
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    command: celery -A app.core.celery_worker worker --loglevel=info

  # Celery Beat (스케줄러)
  celery-beat:
    build:
      context: .
      dockerfile: docker/celery/Dockerfile
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.prod
    depends_on:
      - postgres
      - redis
      - rabbitmq
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    command: celery -A app.core.celery_worker beat --loglevel=info

  # PostgreSQL
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: nebula_ai
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

  # RabbitMQ
  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped

  # Nginx (리버스 프록시)
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/nginx/ssl:/etc/nginx/ssl
    depends_on:
      - ai-server
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
```

### 3. Kubernetes 배포

#### Helm Chart 사용 배포

**charts/nebula-ai/values.yaml**
```yaml
# 전역 설정
global:
  environment: production
  imageRegistry: your-registry.com
  imageTag: "latest"

# AI 서버 설정
aiServer:
  replicaCount: 3
  image:
    repository: nebula-ai/ai-server
    tag: "latest"
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 4Gi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

# Celery Worker 설정
celeryWorker:
  replicaCount: 5
  image:
    repository: nebula-ai/celery-worker
    tag: "latest"
  resources:
    requests:
      cpu: 200m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 2Gi
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 80

# 데이터베이스 설정
postgresql:
  enabled: true
  primary:
    persistence:
      size: 100Gi
    resources:
      requests:
        cpu: 1000m
        memory: 2Gi

redis:
  enabled: true
  master:
    persistence:
      size: 20Gi

rabbitmq:
  enabled: true
  persistence:
    size: 20Gi
```

#### Helm 배포 명령어
```bash
# 1. Helm 차트 의존성 업데이트
helm dependency update charts/nebula-ai

# 2. 네임스페이스 생성
kubectl create namespace nebula-ai

# 3. Secret 생성 (환경 변수)
kubectl create secret generic nebula-ai-secrets \
  --from-env-file=.env.prod \
  --namespace=nebula-ai

# 4. Helm 설치
helm install nebula-ai ./charts/nebula-ai \
  --namespace nebula-ai \
  --values charts/nebula-ai/values.production.yaml

# 5. 배포 상태 확인
kubectl get pods -n nebula-ai
helm status nebula-ai -n nebula-ai
```

### 4. AWS EKS 배포

#### EKS 클러스터 설정 (Terraform)
```hcl
# terraform/eks.tf
module "eks" {
  source = "terraform-aws-modules/eks/aws"
  
  cluster_name    = "nebula-ai-cluster"
  cluster_version = "1.25"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  node_groups = {
    main = {
      desired_size = 3
      max_size     = 10
      min_size     = 1
      
      instance_types = ["t3.large"]
      
      k8s_labels = {
        Environment = "production"
        Application = "nebula-ai"
      }
    }
  }
}
```

#### EKS 배포 명령어
```bash
# 1. Terraform으로 인프라 생성
cd terraform
terraform init
terraform plan
terraform apply

# 2. kubectl 설정
aws eks update-kubeconfig --region us-west-2 --name nebula-ai-cluster

# 3. Helm으로 애플리케이션 배포
helm install nebula-ai ./charts/nebula-ai \
  --namespace nebula-ai \
  --create-namespace \
  --values charts/nebula-ai/values.aws.yaml
```

---

## 환경 설정 관리

### 1. 환경 변수 구성

#### 개발 환경 (.env.dev)
```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# 로컬 서비스 주소
DATABASE_URL=postgresql://postgres:password@localhost:5433/nebula_ai
REDIS_URL=redis://localhost:6380/0
RABBITMQ_URL=amqp://guest:guest@localhost:5673//

# 개발용 API 키
OPENAI_API_KEY=sk-dev-...
ANTHROPIC_API_KEY=sk-ant-dev-...
```

#### 프로덕션 환경 (.env.prod)
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# 프로덕션 데이터베이스
DATABASE_URL=postgresql://user:password@prod-db.amazonaws.com:5432/nebula_ai
REDIS_URL=redis://prod-redis.amazonaws.com:6379/0
RABBITMQ_URL=amqp://user:password@prod-rabbitmq.amazonaws.com:5672//

# 프로덕션 API 키
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# 성능 설정
MAX_WORKERS=8
CELERY_CONCURRENCY=4
REDIS_MAX_CONNECTIONS=50
```

### 2. Secret 관리

#### Kubernetes Secret
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: nebula-ai-secrets
  namespace: nebula-ai
type: Opaque
data:
  openai-api-key: <base64-encoded-key>
  anthropic-api-key: <base64-encoded-key>
  database-url: <base64-encoded-url>
```

#### AWS Secret Manager 통합
```python
# app/core/config.py
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name: str) -> str:
    """AWS Secret Manager에서 시크릿 조회"""
    session = boto3.session.Session()
    client = session.client('secretsmanager', region_name='us-west-2')
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise e
```

---

## 모니터링 및 로깅

### 1. 로그 관리

#### 로그 설정 (docker-compose.yml)
```yaml
services:
  ai-server:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
    volumes:
      - ./logs:/app/logs
```

#### 중앙화된 로깅 (ELK Stack)
```yaml
# 로그 수집 (Filebeat)
filebeat:
  image: elastic/filebeat:8.0.0
  volumes:
    - ./logs:/var/log/nebula-ai
    - ./docker/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml
  depends_on:
    - elasticsearch

# 로그 저장 (Elasticsearch)
elasticsearch:
  image: elastic/elasticsearch:8.0.0
  environment:
    - discovery.type=single-node
    - ES_JAVA_OPTS=-Xms1g -Xmx1g

# 로그 시각화 (Kibana)
kibana:
  image: elastic/kibana:8.0.0
  ports:
    - "5601:5601"
  depends_on:
    - elasticsearch
```

### 2. 메트릭 모니터링

#### Prometheus 설정
```yaml
# docker/monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'nebula-ai'
    static_configs:
      - targets: ['ai-server:8000']
    metrics_path: '/metrics'
    
  - job_name: 'celery'
    static_configs:
      - targets: ['celery-worker:9090']
```

#### Grafana 대시보드
```yaml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  volumes:
    - grafana_data:/var/lib/grafana
    - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin123
```

---

## 백업 및 복구

### 1. 데이터베이스 백업

#### 자동 백업 스크립트
```bash
#!/bin/bash
# scripts/backup_db.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="nebula_ai"

# PostgreSQL 백업
pg_dump -h ${DB_HOST} -U ${DB_USER} -d ${DB_NAME} \
  --no-password --verbose --clean --no-owner --no-privileges \
  > ${BACKUP_DIR}/nebula_ai_${DATE}.sql

# S3로 업로드
aws s3 cp ${BACKUP_DIR}/nebula_ai_${DATE}.sql \
  s3://nebula-ai-backups/database/

# 로컬 파일 정리 (7일 이상 된 파일 삭제)
find ${BACKUP_DIR} -name "*.sql" -mtime +7 -delete
```

#### Kubernetes CronJob으로 백업 자동화
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: database-backup
  namespace: nebula-ai
spec:
  schedule: "0 2 * * *"  # 매일 새벽 2시
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > /backup/backup_$(date +%Y%m%d).sql
              aws s3 cp /backup/backup_$(date +%Y%m%d).sql s3://nebula-ai-backups/
            env:
            - name: DB_HOST
              value: "postgres-service"
            - name: DB_USER
              value: "postgres"
            - name: DB_NAME
              value: "nebula_ai"
          restartPolicy: OnFailure
```

### 2. 데이터 복구

#### 복구 스크립트
```bash
#!/bin/bash
# scripts/restore_db.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# S3에서 백업 파일 다운로드
aws s3 cp s3://nebula-ai-backups/database/${BACKUP_FILE} ./

# 데이터베이스 복구
psql -h ${DB_HOST} -U ${DB_USER} -d ${DB_NAME} < ${BACKUP_FILE}

echo "Database restored from ${BACKUP_FILE}"
```

---

## 성능 최적화

### 1. 스케일링 전략

#### 수평적 확장
```yaml
# HorizontalPodAutoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-server-hpa
  namespace: nebula-ai
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-server
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### 수직적 확장
```yaml
# VerticalPodAutoscaler
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: ai-server-vpa
  namespace: nebula-ai
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-server
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: ai-server
      maxAllowed:
        cpu: 4
        memory: 8Gi
      minAllowed:
        cpu: 200m
        memory: 512Mi
```

### 2. 캐시 최적화

#### Redis 클러스터 설정
```yaml
# Redis 클러스터 (docker-compose)
redis-cluster:
  image: redis:7-alpine
  command: redis-cli --cluster create 
    redis-node-1:6379 redis-node-2:6379 redis-node-3:6379
    --cluster-replicas 1 --cluster-yes
  depends_on:
    - redis-node-1
    - redis-node-2
    - redis-node-3
```

#### 캐시 전략 설정
```python
# app/core/cache_config.py
CACHE_STRATEGIES = {
    "user_profile": {
        "ttl": 3600,  # 1시간
        "strategy": "write_through"
    },
    "recommendations": {
        "ttl": 1800,  # 30분
        "strategy": "cache_aside"
    },
    "similar_users": {
        "ttl": 7200,  # 2시간
        "strategy": "write_behind"
    }
}
```

---

## 보안 설정

### 1. 네트워크 보안

#### 방화벽 설정 (iptables)
```bash
# 필요한 포트만 개방
iptables -A INPUT -p tcp --dport 22 -j ACCEPT   # SSH
iptables -A INPUT -p tcp --dport 80 -j ACCEPT   # HTTP
iptables -A INPUT -p tcp --dport 443 -j ACCEPT  # HTTPS
iptables -A INPUT -j DROP                       # 나머지 차단
```

#### Kubernetes Network Policy
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: nebula-ai-network-policy
  namespace: nebula-ai
spec:
  podSelector:
    matchLabels:
      app: ai-server
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

### 2. SSL/TLS 설정

#### Let's Encrypt 인증서 자동 갱신
```yaml
# cert-manager 설정
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```

### 3. 애플리케이션 보안

#### 보안 헤더 설정 (Nginx)
```nginx
# docker/nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name api.nebula-ai.com;
    
    # 보안 헤더
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    add_header Content-Security-Policy "default-src 'self'";
    
    # API 프록시
    location / {
        proxy_pass http://ai-server:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## CI/CD 파이프라인

### 1. GitHub Actions

#### 빌드 및 테스트 파이프라인
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install pipenv
        pipenv install --dev
    
    - name: Run tests
      run: |
        pipenv run pytest tests/ -v --cov=app
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t nebula-ai:${{ github.sha }} .
        docker tag nebula-ai:${{ github.sha }} nebula-ai:latest
    
    - name: Push to registry
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker push nebula-ai:${{ github.sha }}
        docker push nebula-ai:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Deploy to production
      run: |
        # kubectl 설정 및 배포
        echo "${{ secrets.KUBECONFIG }}" | base64 -d > kubeconfig
        export KUBECONFIG=kubeconfig
        
        helm upgrade nebula-ai ./charts/nebula-ai \
          --namespace nebula-ai \
          --set image.tag=${{ github.sha }}
```

### 2. ArgoCD GitOps

#### Application 설정
```yaml
# gitops/applications/nebula-ai.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: nebula-ai
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/nebula-ai
    targetRevision: HEAD
    path: charts/nebula-ai
    helm:
      valueFiles:
      - values.production.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: nebula-ai
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

---

## 트러블슈팅

### 1. 일반적인 문제들

#### 메모리 부족
```bash
# 증상: OOM Killer에 의한 Pod 종료
# 해결: 리소스 한계 증가
kubectl patch deployment ai-server -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "ai-server",
          "resources": {
            "limits": {
              "memory": "4Gi"
            }
          }
        }]
      }
    }
  }
}'
```

#### 데이터베이스 연결 문제
```bash
# 연결 풀 설정 확인
kubectl logs deployment/ai-server | grep "connection"

# 연결 수 모니터링
kubectl exec -it postgres-pod -- psql -c "
SELECT state, count(*) 
FROM pg_stat_activity 
GROUP BY state;
"
```

#### RabbitMQ 큐 백로그
```bash
# 큐 상태 확인
kubectl exec -it rabbitmq-pod -- rabbitmqctl list_queues

# Consumer 확장
kubectl scale deployment celery-worker --replicas=10
```

### 2. 성능 문제 진단

#### 응답 시간 측정
```bash
# API 응답 시간 테스트
curl -w "@curl-format.txt" -o /dev/null -s "http://api.nebula-ai.com/health"

# curl-format.txt 내용:
#     time_namelookup:  %{time_namelookup}\n
#        time_connect:  %{time_connect}\n
#     time_appconnect:  %{time_appconnect}\n
#    time_pretransfer:  %{time_pretransfer}\n
#       time_redirect:  %{time_redirect}\n
#  time_starttransfer:  %{time_starttransfer}\n
#                     ----------\n
#          time_total:  %{time_total}\n
```

#### 데이터베이스 쿼리 분석
```sql
-- 느린 쿼리 확인
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- 활성 연결 확인
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';
```

---

## 배포 체크리스트

### 배포 전 확인사항
- [ ] 모든 테스트 통과 확인
- [ ] 환경 변수 설정 완료
- [ ] 데이터베이스 마이그레이션 준비
- [ ] SSL 인증서 준비 (프로덕션)
- [ ] 모니터링 설정 확인
- [ ] 백업 시스템 확인

### 배포 후 확인사항
- [ ] 모든 서비스 정상 동작 확인
- [ ] API 응답 테스트
- [ ] 데이터베이스 연결 확인
- [ ] 메시지 큐 동작 확인
- [ ] 로그 및 메트릭 수집 확인
- [ ] 알림 시스템 테스트

### 롤백 계획
- [ ] 이전 버전 이미지 보관
- [ ] 데이터베이스 스키마 버전 관리
- [ ] 설정 파일 버전 관리
- [ ] 롤백 스크립트 준비

---

이 배포 가이드는 Nebula AI 시스템의 안정적이고 확장 가능한 배포를 위한 포괄적인 지침을 제공합니다. 환경에 따라 적절히 조정하여 사용하시기 바랍니다. 