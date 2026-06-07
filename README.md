# vm-resize-agent

Auto-resize your EC2 instance when a data pipeline completes.

No more paying for a large VM sitting idle after your data loading job finishes.

---

## The Problem

Data pipelines need big machines. APIs don't.

```
t3.large running pipeline  →  pipeline done at 3AM
t3.large sitting idle       →  you're paying $0.08/hr for nothing
```

This tool solves that. When your pipeline finishes, the VM automatically downsizes itself.

---

## How It Works

```
Pipeline finishes (success or failure)
        ↓
emit_event.py fires → EventBridge
        ↓
Lambda triggered
        ↓
SUCCESS → VM resizes down + email alert
FAILURE → VM stays same size (for debugging) + email alert
```

---

## Architecture

```
Your VM                        AWS Cloud
──────────────────             ──────────────────────────
run_pipeline.sh                EventBridge (custom bus)
  step1                   →         ↓
  step2                        Lambda
  step3                          ├── resize EC2
  emit_event.py ──────────→      └── SNS email alert
```

---

## Project Structure

```
vm-resize-agent/
├── infra/
│   └── template.yaml       ← deploys all AWS resources
├── agent/
│   └── emit_event.py       ← runs on your VM
├── pipeline/
│   ├── run_pipeline.sh     ← generic wrapper (never edit)
│   └── steps.conf          ← your pipeline steps go here
└── demo/
    ├── demo_pipeline.py    ← sample pipeline (weather data)
    └── docker-compose.yml  ← postgres for demo
```

---

## Prerequisites

- AWS CLI installed and configured (`aws configure`)
- Python 3.8+ on your VM
- boto3 (`pip install boto3`)
- EC2 instance tagged `Name=vm-resize-agent-demo`

---

## Setup (3 steps)

### Step 1 — Deploy AWS infrastructure

```bash
git clone https://github.com/yourname/vm-resize-agent
cd vm-resize-agent

aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name vm-resize-agent \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      AlertEmail=your@email.com \
      TargetInstanceType=t3.medium \
  --region us-east-1
```

Check your email → confirm the AWS subscription link.

### Step 2 — Copy agent to your VM

```bash
scp -i your-key.pem -r agent/ pipeline/ user@your-vm-ip:~/vm-resize-agent/
```

On your VM install dependency:

```bash
pip install boto3
aws configure   # enter your AWS credentials
```

### Step 3 — Add your pipeline steps

Edit `pipeline/steps.conf` on your VM:

```bash
# Add your pipeline commands, one per line
python3 /home/user/myproject/fetch_data.py
python3 /home/user/myproject/transform.py
python3 /home/user/myproject/load_db.py
```

Then run:

```bash
cd ~/vm-resize-agent
bash pipeline/run_pipeline.sh
```

That's it. When pipeline finishes → VM resizes automatically → email arrives.

---

## Tag your EC2

The agent finds your VM by tag. Make sure your EC2 has:

```
Key:   Name
Value: vm-resize-agent-demo
```

Or change the tag value in `infra/template.yaml` to match your existing tag.

---

## Trigger Options

All four trigger types work out of the box:

```bash
# nohup (runs in background, survives logout)
nohup bash pipeline/run_pipeline.sh > pipeline.log 2>&1 &

# tmux (recommended - attach/detach anytime)
tmux new -s pipeline "bash pipeline/run_pipeline.sh"

# systemd (runs as a service)
# add to your .service file:
ExecStart=/bin/bash /home/user/vm-resize-agent/pipeline/run_pipeline.sh

# cron (scheduled)
0 2 * * * bash /home/user/vm-resize-agent/pipeline/run_pipeline.sh
```

---

## Email Alerts

**Success:**
```
Pipeline: data-loader
Status:   SUCCESS
Steps:    3/3
Duration: 45m 12s
Instance: i-0abc123
Resized:  Yes -> t3.medium
```

**Failure:**
```
Pipeline:  data-loader
Status:    FAILURE
Steps:     2/3
Duration:  18s
Failed at: step_3
Instance:  i-0abc123
Resized:   No (kept original size for debugging)
```

On failure — VM is intentionally NOT resized so you can SSH in and debug.

---

## Important Notes

**Elastic IP** — assign a static IP to your VM so SSH access works after resize:

```bash
aws ec2 allocate-address --region us-east-1
aws ec2 associate-address --instance-id i-xxx --allocation-id eipalloc-xxx
```

**Docker/services** — after resize, VM reboots. Add startup script to restart your services:

```bash
# /etc/rc.local
sudo service docker start
cd /home/user/myproject && docker-compose up -d
```

**Resize back up** — before next pipeline run, resize back to large manually or via cron:

```bash
aws ec2 stop-instances --instance-ids i-xxx
aws ec2 modify-instance-attribute --instance-id i-xxx --instance-type t3.large
aws ec2 start-instances --instance-ids i-xxx
```

---

## Cleanup

```bash
aws cloudformation delete-stack \
  --stack-name vm-resize-agent \
  --region us-east-1
```

Removes all AWS resources (Lambda, EventBridge, SNS, IAM role).

---

## Cost

| Resource | Cost |
|---|---|
| EventBridge | ~$0/month (free tier) |
| Lambda | ~$0/month (free tier) |
| SNS email | ~$0/month (first 1000 free) |
| **Total stack** | **~$0/month** |

Savings depend on your instance size and idle hours. A t3.large idle for 20hrs/day saves ~$25/month.

---

## Demo

The `demo/` folder contains a working example that downloads a real weather dataset, loads it into Postgres, and triggers the resize automatically.

### Run the demo

**1. Launch EC2 with correct tag:**

```bash
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.large \
  --key-name your-key-name \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=vm-resize-agent-demo}]' \
  --region us-east-1
```

**2. Assign Elastic IP (so IP stays same after resize):**

```bash
aws ec2 allocate-address --region us-east-1
aws ec2 associate-address \
  --instance-id i-xxx \
  --allocation-id eipalloc-xxx \
  --region us-east-1
```

**3. SSH in and set up:**

```bash
ssh -i your-key.pem ec2-user@your-elastic-ip

# install dependencies
sudo yum install -y python3 python3-pip docker
sudo service docker start
sudo usermod -a -G docker ec2-user

# re-login for docker group to apply
exit && ssh -i your-key.pem ec2-user@your-elastic-ip

pip3 install boto3 pandas psycopg2-binary requests
pip3 install urllib3==1.26.18  # Amazon Linux 2 fix

aws configure  # enter your AWS credentials
```

**4. Copy project files to VM:**

```bash
scp -i your-key.pem -r agent/ pipeline/ demo/ \
  ec2-user@your-elastic-ip:~/vm-resize-agent/
```

**5. Start Postgres and run demo:**

```bash
cd ~/vm-resize-agent/demo
docker-compose up -d

echo "python3 /home/ec2-user/vm-resize-agent/demo/demo_pipeline.py" \
  > ~/vm-resize-agent/pipeline/steps.conf

cd ~/vm-resize-agent
bash pipeline/run_pipeline.sh
```

Pipeline runs → loads weather data into Postgres → VM resizes automatically → email arrives.

---

## Resizing Back Up

After pipeline completes VM is downsized. Before next data load, resize back up:

```bash
aws ec2 stop-instances --instance-ids i-xxx --region us-east-1
aws ec2 wait instance-stopped --instance-ids i-xxx --region us-east-1
aws ec2 modify-instance-attribute \
  --instance-id i-xxx \
  --instance-type t3.large \
  --region us-east-1
aws ec2 start-instances --instance-ids i-xxx --region us-east-1
```

Or automate with cron:

```bash
# resize up at 1AM, run pipeline at 2AM
0 1 * * * aws ec2 stop-instances --instance-ids i-xxx && \
           aws ec2 modify-instance-attribute --instance-id i-xxx --instance-type t3.large && \
           aws ec2 start-instances --instance-ids i-xxx
0 2 * * * bash /home/user/vm-resize-agent/pipeline/run_pipeline.sh
```

---

## License

MIT
