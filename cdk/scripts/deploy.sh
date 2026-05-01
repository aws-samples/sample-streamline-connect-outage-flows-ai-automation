#!/bin/bash

# Supervisor AI Agent CDK Deployment Script
# This script validates prerequisites and deploys the CDK stack with proper configuration

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CDK_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$CDK_DIR")"
REQUIRED_NODE_VERSION="18"
REQUIRED_AWS_CLI_VERSION="2"

# Default values
AWS_PROFILE="${AWS_PROFILE:-joysl-auto-tfc-Admin}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SKIP_VALIDATION="${SKIP_VALIDATION:-false}"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to compare versions
version_ge() {
    [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

# Function to validate Node.js version
validate_node() {
    print_info "Checking Node.js installation..."
    
    if ! command_exists node; then
        print_error "Node.js is not installed"
        print_info "Please install Node.js ${REQUIRED_NODE_VERSION}.x or higher from https://nodejs.org/"
        return 1
    fi
    
    local node_version=$(node --version | sed 's/v//' | cut -d. -f1)
    if [ "$node_version" -lt "$REQUIRED_NODE_VERSION" ]; then
        print_error "Node.js version $node_version is too old"
        print_info "Please upgrade to Node.js ${REQUIRED_NODE_VERSION}.x or higher"
        return 1
    fi
    
    print_success "Node.js $(node --version) detected"
    return 0
}

# Function to validate npm
validate_npm() {
    print_info "Checking npm installation..."
    
    if ! command_exists npm; then
        print_error "npm is not installed"
        return 1
    fi
    
    print_success "npm $(npm --version) detected"
    return 0
}

# Function to validate AWS CLI
validate_aws_cli() {
    print_info "Checking AWS CLI installation..."
    
    if ! command_exists aws; then
        print_error "AWS CLI is not installed"
        print_info "Please install AWS CLI v2 from https://aws.amazon.com/cli/"
        return 1
    fi
    
    local aws_version=$(aws --version 2>&1 | cut -d/ -f2 | cut -d. -f1)
    if [ "$aws_version" -lt "$REQUIRED_AWS_CLI_VERSION" ]; then
        print_warning "AWS CLI v1 detected. AWS CLI v2 is recommended"
    else
        print_success "AWS CLI v${aws_version} detected"
    fi
    
    return 0
}

# Function to validate AWS credentials
validate_aws_credentials() {
    print_info "Checking AWS credentials for profile: $AWS_PROFILE"
    
    if ! aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" >/dev/null 2>&1; then
        print_error "Failed to authenticate with AWS profile: $AWS_PROFILE"
        print_info "Please configure your AWS credentials:"
        print_info "  aws configure --profile $AWS_PROFILE"
        return 1
    fi
    
    local account_id=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" --query Account --output text)
    local user_arn=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" --query Arn --output text)
    
    print_success "Authenticated as: $user_arn"
    print_success "Account ID: $account_id"
    print_success "Region: $AWS_REGION"
    
    return 0
}

# Function to validate CDK bootstrap
validate_cdk_bootstrap() {
    print_info "Checking CDK bootstrap status..."
    
    local account_id=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" --query Account --output text)
    local bootstrap_stack_name="CDKToolkit"
    
    if ! aws cloudformation describe-stacks \
        --stack-name "$bootstrap_stack_name" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" >/dev/null 2>&1; then
        print_warning "CDK is not bootstrapped in this account/region"
        print_info "Run the following command to bootstrap CDK:"
        print_info "  cd $CDK_DIR && cdk bootstrap aws://$account_id/$AWS_REGION --profile $AWS_PROFILE"
        
        read -p "Would you like to bootstrap now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Bootstrapping CDK..."
            cd "$CDK_DIR"
            cdk bootstrap "aws://$account_id/$AWS_REGION" --profile "$AWS_PROFILE"
            print_success "CDK bootstrap completed"
        else
            print_error "CDK bootstrap is required for deployment"
            return 1
        fi
    else
        print_success "CDK is bootstrapped"
    fi
    
    return 0
}

# Function to validate CDK dependencies
validate_cdk_dependencies() {
    print_info "Checking CDK dependencies..."
    
    cd "$CDK_DIR"
    
    if [ ! -d "node_modules" ]; then
        print_warning "CDK dependencies not installed"
        print_info "Installing dependencies..."
        npm install
        print_success "Dependencies installed"
    else
        print_success "CDK dependencies found"
    fi
    
    return 0
}

# Function to validate Python environment
validate_python() {
    print_info "Checking Python installation..."
    
    if ! command_exists python3.12; then
        print_error "Python 3.12 is not installed"
        print_info "Please install Python 3.12 from https://www.python.org/"
        return 1
    fi
    
    print_success "Python $(python3.12 --version) detected"
    return 0
}

# Function to validate Python virtual environment
validate_python_venv() {
    print_info "Checking Python virtual environment..."
    
    cd "$PROJECT_ROOT"
    
    if [ ! -d "venv" ]; then
        print_warning "Python virtual environment not found"
        print_info "Creating virtual environment..."
        python3.12 -m venv venv
        print_success "Virtual environment created"
        
        print_info "Installing Python dependencies..."
        source venv/bin/activate
        pip install -r lambda/requirements.txt
        deactivate
        print_success "Python dependencies installed"
    else
        print_success "Python virtual environment found"
    fi
    
    return 0
}

# Function to validate CDK parameters
validate_parameters() {
    print_info "Validating CDK parameters..."
    
    local missing_params=()
    
    # Check for required context parameters
    if [ -z "$(cd "$CDK_DIR" && npx cdk context --profile "$AWS_PROFILE" 2>/dev/null | grep connectInstanceId)" ]; then
        missing_params+=("connectInstanceId")
    fi
    
    if [ -z "$(cd "$CDK_DIR" && npx cdk context --profile "$AWS_PROFILE" 2>/dev/null | grep qConnectAssistantId)" ]; then
        missing_params+=("qConnectAssistantId")
    fi
    
    if [ ${#missing_params[@]} -gt 0 ]; then
        print_warning "The following parameters are not set in cdk.context.json:"
        for param in "${missing_params[@]}"; do
            echo "  - $param"
        done
        print_info "You can set these parameters in cdk.context.json or pass them during deployment"
        print_info "Example: cdk deploy -c connectInstanceId=xxx -c qConnectAssistantId=yyy"
    else
        print_success "Required parameters are configured"
    fi
    
    return 0
}

# Function to build CDK project
build_cdk() {
    print_info "Building CDK project..."
    
    cd "$CDK_DIR"
    npm run build
    
    if [ $? -eq 0 ]; then
        print_success "CDK build completed"
        return 0
    else
        print_error "CDK build failed"
        return 1
    fi
}

# Function to synthesize CDK stack
synthesize_stack() {
    print_info "Synthesizing CDK stack..."
    
    cd "$CDK_DIR"
    cdk synth --profile "$AWS_PROFILE" --region "$AWS_REGION"
    
    if [ $? -eq 0 ]; then
        print_success "CDK synthesis completed"
        return 0
    else
        print_error "CDK synthesis failed"
        return 1
    fi
}

# Function to deploy CDK stack
deploy_stack() {
    print_info "Deploying CDK stack..."
    print_warning "This operation will create AWS resources and may incur costs"
    
    read -p "Do you want to proceed with deployment? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled"
        return 1
    fi
    
    cd "$CDK_DIR"
    
    print_info "Starting deployment (this may take several minutes)..."
    print_warning "Please run the following command manually and paste the output when complete:"
    echo ""
    echo "cd $CDK_DIR && cdk deploy --profile $AWS_PROFILE --region $AWS_REGION --require-approval never"
    echo ""
    
    return 0
}

# Function to show deployment outputs
show_outputs() {
    print_info "Retrieving stack outputs..."
    
    local stack_name="SupervisorAIAgentStack"
    
    if aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" >/dev/null 2>&1; then
        
        print_success "Stack outputs:"
        aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --profile "$AWS_PROFILE" \
            --region "$AWS_REGION" \
            --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
            --output table
    else
        print_warning "Stack not found or not yet deployed"
    fi
}

# Main execution
main() {
    print_header "Supervisor AI Agent CDK Deployment"
    
    print_info "Configuration:"
    echo "  AWS Profile: $AWS_PROFILE"
    echo "  AWS Region: $AWS_REGION"
    echo "  CDK Directory: $CDK_DIR"
    echo "  Project Root: $PROJECT_ROOT"
    echo ""
    
    # Run validations unless skipped
    if [ "$SKIP_VALIDATION" != "true" ]; then
        print_header "Pre-Deployment Validation"
        
        validate_node || exit 1
        validate_npm || exit 1
        validate_aws_cli || exit 1
        validate_aws_credentials || exit 1
        validate_python || exit 1
        validate_python_venv || exit 1
        validate_cdk_dependencies || exit 1
        validate_cdk_bootstrap || exit 1
        validate_parameters
        
        print_success "All validations passed"
    else
        print_warning "Skipping pre-deployment validation"
    fi
    
    # Build and synthesize
    print_header "Build and Synthesis"
    
    build_cdk || exit 1
    synthesize_stack || exit 1
    
    # Deploy
    print_header "Deployment"
    
    deploy_stack
    
    # Show outputs
    print_header "Deployment Complete"
    
    print_success "CDK deployment script completed"
    print_info "Next steps:"
    echo "  1. Complete the manual deployment command shown above"
    echo "  2. Review stack outputs for integration values"
    echo "  3. Follow the manual setup guides in docs/manual-setup/"
    echo "  4. Configure Amazon Connect Contact Flow"
    echo "  5. Configure Amazon Lex PIN Bot"
    echo "  6. Configure Supervisor AI Agent"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --skip-validation)
            SKIP_VALIDATION="true"
            shift
            ;;
        --outputs-only)
            show_outputs
            exit 0
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --profile PROFILE       AWS profile to use (default: joysl-auto-tfc-Admin)"
            echo "  --region REGION         AWS region to deploy to (default: us-east-1)"
            echo "  --skip-validation       Skip pre-deployment validation checks"
            echo "  --outputs-only          Show stack outputs only (no deployment)"
            echo "  --help                  Show this help message"
            echo ""
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main
